import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import AuthError
from src.config import settings

logger = logging.getLogger(__name__)

class Neo4jStore:
    """Handles Neo4j interactions for TieredMemory."""

    def __init__(self, neo4j_uri: Optional[str] = None, neo4j_user: Optional[str] = None, neo4j_password: Optional[str] = None):
        self.neo4j_uri = neo4j_uri or settings.neo4j_uri
        self.neo4j_user = neo4j_user or settings.neo4j_user
        self.neo4j_password = neo4j_password or settings.neo4j_password
        self.neo4j_driver = None
        self._neo4j_reconnect_task = None
        self._neo4j_reconnect_attempts = 0
        self._neo4j_auth_error = False

    async def initialize(self):
        """Connect to Neo4j."""
        if not getattr(settings, "neo4j_enabled", True):
            logger.info("Neo4j disabled by configuration")
            return

        try:
            self.neo4j_driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            async with self.neo4j_driver.session() as session:
                await session.run("RETURN 1")
                # Create schema indexes to prevent warnings and improve performance
                await session.run("CREATE INDEX memory_category IF NOT EXISTS FOR (n:Memory) ON (n.category)")
                await session.run("CREATE INDEX memory_created_at IF NOT EXISTS FOR (n:Memory) ON (n.created_at)")
                await session.run("CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)")
                # Index for deduplication by content hash
                await session.run("CREATE INDEX memory_content_hash IF NOT EXISTS FOR (n:Memory) ON (n.content_hash)")
                # Indexes to support provenance/freshness-driven queries
                await session.run("CREATE INDEX memory_provenance_score IF NOT EXISTS FOR (n:Memory) ON (n.provenance_score)")
                await session.run("CREATE INDEX memory_freshness_score IF NOT EXISTS FOR (n:Memory) ON (n.freshness_score)")
            logger.info("Neo4j connected")
        except Exception as e:
            logger.warning(f"Neo4j unavailable: {e}")
            if isinstance(e, AuthError) or "unauthorized" in str(e).lower():
                self._neo4j_auth_error = True
            self.neo4j_driver = None
            if getattr(settings, 'neo4j_reconnect_enabled', False) and not self._neo4j_auth_error:
                self._neo4j_reconnect_task = asyncio.create_task(self._neo4j_reconnect_loop())

    async def close(self):
        """Close Neo4j connection."""
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        if self._neo4j_reconnect_task:
            self._neo4j_reconnect_task.cancel()

    async def _neo4j_reconnect_loop(self):
        """Background retry loop."""
        delay = getattr(settings, 'neo4j_reconnect_initial_delay', 5)
        max_attempts = getattr(settings, 'neo4j_reconnect_max_attempts', 6)
        backoff = getattr(settings, 'neo4j_reconnect_backoff_factor', 2.0)
        attempt = 0
        
        while attempt < max_attempts and self.neo4j_driver is None:
            attempt += 1
            try:
                driver = AsyncGraphDatabase.driver(
                    self.neo4j_uri,
                    auth=(self.neo4j_user, self.neo4j_password)
                )
                async with driver.session() as session:
                    await session.run("RETURN 1")
                self.neo4j_driver = driver
                logger.info("Neo4j reconnected successfully")
                break
            except Exception as e:
                if isinstance(e, AuthError):
                    self._neo4j_auth_error = True
                    break
                await asyncio.sleep(delay)
                delay *= backoff

    async def trigger_reconnect(self, force: bool = False) -> dict:
        """Trigger a reconnect loop for Neo4j. If force is True, close any existing driver and start a new reconnect."""
        if force and self.neo4j_driver:
            try:
                await self.neo4j_driver.close()
            except Exception:
                pass
            self.neo4j_driver = None

        if self._neo4j_auth_error:
            return {"started": False, "message": "Neo4j auth error; credential fix required"}

        # If a reconnect task is already running, return status
        if self._neo4j_reconnect_task and not self._neo4j_reconnect_task.done():
            return {"started": False, "message": "Reconnect already in progress"}

        self._neo4j_reconnect_task = asyncio.create_task(self._neo4j_reconnect_loop())
        return {"started": True}

    async def execute_cypher(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute raw Cypher query."""
        if not self.neo4j_driver:
            return []
        try:
            async with self.neo4j_driver.session() as session:
                result = await session.run(query, params or {})
                return await result.data()
        except Exception as e:
            logger.error(f"Cypher execution failed: {e}")
            return []

    async def add_memory(self, session_id: str, content: str, category: str, tags: List[str], importance: int, metadata: Dict[str, Any], entities: List[Dict[str, Any]] = None, content_cleaned: str = None, content_hash: str = None, content_embedding_text: str = None):
        """Add memory node and link entities."""
        if not self.neo4j_driver:
            return
        try:
            async with self.neo4j_driver.session() as session:
                # Compute / enforce app_id inside metadata if missing
                if metadata is None:
                    metadata = {}
                # Prefer provided app_id in metadata, otherwise compute deterministically
                app_id = None
                try:
                    if isinstance(metadata, dict) and metadata.get('app_id'):
                        app_id = str(metadata.get('app_id'))
                    elif isinstance(metadata, dict) and metadata.get('source') and metadata.get('chunk_index') is not None:
                        import uuid
                        ns = uuid.UUID('f8bd0f6e-0c4c-4654-9201-12c4f2b4b5ef')
                        app_id = str(uuid.uuid5(ns, f"{metadata.get('source')}:{metadata.get('chunk_index')}"))
                    else:
                        import uuid
                        ns = uuid.UUID('f8bd0f6e-0c4c-4654-9201-12c4f2b4b5ef')
                        app_id = str(uuid.uuid5(ns, (content or '')[:4096]))
                except Exception:
                    # Fallback to uuid4 if anything goes wrong
                    import uuid
                    app_id = str(uuid.uuid4())
                # Write app_id back into metadata JSON for consistency
                if isinstance(metadata, dict):
                    metadata['app_id'] = app_id
                else:
                    # if metadata is a string, attempt to parse and re-serialize with app_id
                    try:
                        md = json.loads(metadata) if isinstance(metadata, str) and metadata else {}
                        md['app_id'] = app_id
                        metadata = md
                    except Exception:
                        metadata = {'app_id': app_id}

                # Deduplication: if a content_hash exists, check if we've already stored it
                if content_hash:
                    dedup_q = "MATCH (m:Memory) WHERE m.content_hash = $content_hash RETURN elementId(m) as id LIMIT 1"
                    dedup_res = await session.run(dedup_q, {'content_hash': content_hash})
                    dedup_rec = await dedup_res.single()
                    if dedup_rec and dedup_rec.get('id'):
                        # Found existing memory; do not create duplicate
                        return dedup_rec.get('id')

                # Compute provenance_score and freshness_score defaults
                def _derive_provenance_score(meta: Dict[str, Any], category: str) -> float:
                    try:
                        if category:
                            c = category.lower()
                            if c == 'code':
                                return 1.0
                            if c in ('log', 'logs'):
                                return 0.95
                            if c in ('doc', 'docs', 'documentation'):
                                return 0.8
                            if c in ('chat', 'conversation', 'message'):
                                return 0.4
                    except Exception:
                        pass
                    # inspect metadata for source file info
                    try:
                        if isinstance(meta, dict):
                            src = meta.get('source', '')
                            if isinstance(src, str):
                                if src.endswith('.py') or src.endswith('.js'):
                                    return 1.0
                                if src.endswith('.log'):
                                    return 0.95
                            # Source type field
                            if meta.get('source_type') == 'doc':
                                return 0.8
                    except Exception:
                        pass
                    return float(getattr(settings, 'memory_default_provenance_score', 0.5))

                provenance_score = _derive_provenance_score(metadata or {}, category)
                freshness_score = float(getattr(settings, 'memory_default_freshness_score', 1.0))
                # default last_verified_at is None; Verifier will fill it
                last_verified_at = metadata.get('last_verified_at') if isinstance(metadata, dict) else None

                # Create Memory node with app_id property
                result = await session.run(
                    """
                    CREATE (m:Memory {
                        session_id: $session_id,
                        content: $content,
                        content_cleaned: $content_cleaned,
                        content_hash: $content_hash,
                        provenance_score: $provenance_score,
                        freshness_score: $freshness_score,
                        last_verified_at: $last_verified_at,
                        content_embedding_text: $content_embedding_text,
                        category: $category,
                        app_id: $app_id,
                        tags: $tags,
                        importance: $importance,
                        metadata: $metadata,
                        created_at: $created_at
                    })
                    RETURN elementId(m) as id
                    """,
                    {
                        "session_id": session_id or "unknown",
                        "content": content,
                        "content_cleaned": content_cleaned,
                        "content_hash": content_hash,
                        "content_embedding_text": content_embedding_text,
                        "category": category,
                        "app_id": app_id,
                        "tags": tags or [],
                        "importance": importance,
                        "metadata": json.dumps(metadata, default=str) if metadata else None,
                        "provenance_score": provenance_score,
                        "freshness_score": freshness_score,
                        "last_verified_at": last_verified_at,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                )
                record = await result.single()
                memory_id = record["id"] if record else None

                # Link Entities if provided
                if entities and memory_id:
                    await session.run(
                        """
                        MATCH (m:Memory) WHERE elementId(m) = $memory_id
                        UNWIND $entities as ent
                        MERGE (e:Entity {name: ent.text})
                        ON CREATE SET e.type = ent.type, e.metadata = ent.metadata
                        MERGE (m)-[:MENTIONS]->(e)
                        """,
                        {
                            "memory_id": memory_id,
                            "entities": [
                                {
                                    "text": e.get("text"),
                                    "type": e.get("type", "unknown"),
                                    "metadata": json.dumps(e.get("metadata", {}))
                                }
                                for e in entities if e.get("text")
                            ]
                        }
                    )
                
                return memory_id
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return None

    async def search_memories(self, query: str, category: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """Search memories."""
        if not self.neo4j_driver:
            return []
        
        # Prefer fulltext index search for more reliable matches (memorySearch index)
        # Fallback to a CONTAINS search if the fulltext index isn't available or fails.
        cypher_fulltext = """
        CALL db.index.fulltext.queryNodes('memorySearch', $query) YIELD node, score
        WHERE ($category IS NULL OR node.category = $category)
        RETURN elementId(node) as id, node as m, score
        ORDER BY score DESC
        LIMIT $limit
        """
        
        try:
            async with self.neo4j_driver.session() as session:
                try:
                    result = await session.run(cypher_fulltext, {"query": query, "category": category, "limit": limit})
                    records = await result.data()
                except Exception:
                    # If fulltext index isn't available, fallback to an older contains query
                    cypher_contains = """
                    MATCH (m:Memory)
                    WHERE m.content CONTAINS $query
                    """ + ("AND m.category = $category" if category else "") + """
                    RETURN elementId(m) as id, m
                    LIMIT $limit
                    """
                    result = await session.run(cypher_contains, {"query": query, "category": category, "limit": limit})
                    records = await result.data()
                return [self._parse_memory_record(r) for r in records]
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    def _parse_memory_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Neo4j record into standard memory dict."""
        node = record.get("m") or record.get("node")
        eid = record.get("id")
        score = record.get("score")
        
        # Defensive parsing
        tags = node.get("tags")
        if isinstance(tags, str):
            try: tags = json.loads(tags)
            except: tags = [tags]
        
        meta = node.get("metadata")
        if isinstance(meta, str):
            try: meta = json.loads(meta)
            except: meta = {}
            
        return {
            "id": eid,
            "memory_id": eid,
            "content": node.get("content"),
            "tags": tags or [],
            "importance": node.get("importance", 5),
            "session_id": node.get("session_id"),
            "timestamp": node.get("created_at"),
            "category": node.get("category"),
            "metadata": meta or {},
            "score": score if score is not None else node.get("importance", 5) / 10.0
        }

    async def get_recent_by_category(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent memories by category."""
        if not self.neo4j_driver:
            return []
        
        cypher = """
        MATCH (m:Memory)
        WHERE m.category = $category
        RETURN elementId(m) as id, m
        ORDER BY m.created_at DESC
        LIMIT $limit
        """
        try:
            async with self.neo4j_driver.session() as session:
                result = await session.run(cypher, {"category": category, "limit": limit})
                records = await result.data()
                return [self._parse_memory_record(r) for r in records]
        except Exception as e:
            logger.error(f"Failed to get recent memories for category {category}: {e}")
            return []

    async def get_summaries(self, session_id: str, limit: int = 5) -> List[str]:
        """Get recent summaries for a session."""
        if not self.neo4j_driver:
            return []
            
        cypher = """
        MATCH (m:Memory)
        WHERE m.session_id = $session_id AND m.category = 'summary'
        RETURN m.content as content
        ORDER BY m.created_at DESC
        LIMIT $limit
        """
        try:
            async with self.neo4j_driver.session() as session:
                result = await session.run(cypher, {"session_id": session_id, "limit": limit})
                records = await result.data()
                return [r["content"] for r in records if r.get("content")]
        except Exception as e:
            logger.error(f"Failed to get summaries for session {session_id}: {e}")
            return []
