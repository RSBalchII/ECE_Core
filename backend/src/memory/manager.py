import logging
import tiktoken
from typing import Optional, List, Dict, Any
from src.config import settings
from src.content_utils import clean_content, is_json_like, is_html_like, has_technical_signal
import hashlib
from src.vector_adapter import create_vector_adapter
from src.memory.redis_cache import RedisCache
from src.memory.neo4j_store import Neo4jStore
from src.distiller import distill_moment

logger = logging.getLogger(__name__)

class TieredMemory:
    """
    Orchestrator for Tiered Memory (Redis + Neo4j).
    Replaces the monolithic src/memory.py.
    """

    def __init__(self, neo4j_uri: Optional[str] = None, redis_url: Optional[str] = None, neo4j_user: Optional[str] = None, neo4j_password: Optional[str] = None, llm_client=None):
        self.redis = RedisCache(redis_url)
        self.neo4j = Neo4jStore(neo4j_uri, neo4j_user, neo4j_password)
        self.llm_client = llm_client
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Vector support
        self.vector_adapter = None
        self._vector_enabled = getattr(settings, "vector_enabled", False)
        if self._vector_enabled:
            try:
                self.vector_adapter = create_vector_adapter()
            except Exception as e:
                logger.warning(f"Failed to create vector adapter: {e}")

        # Backwards-compatible property accessors for legacy tests & code

    async def initialize(self):
        """Initialize all stores."""
        await self.redis.initialize()
        await self.neo4j.initialize()
        if self.vector_adapter and hasattr(self.vector_adapter, "initialize"):
            await self.vector_adapter.initialize()
        
        # Auto-init LLM for embeddings if needed
        if getattr(settings, "vector_auto_embed", False) and not self.llm_client:
            try:
                from src.llm import LLMClient
                self.llm_client = LLMClient()
            except Exception as e:
                logger.warning(f"Failed to init LLM client for auto-embed: {e}")

    @property
    def neo4j_driver(self):
        return getattr(self.neo4j, 'neo4j_driver', None)

    @neo4j_driver.setter
    def neo4j_driver(self, val):
        if self.neo4j:
            self.neo4j.neo4j_driver = val

    @property
    def neo4j_uri(self):
        return getattr(self.neo4j, 'neo4j_uri', None)

    @neo4j_uri.setter
    def neo4j_uri(self, val):
        if self.neo4j:
            self.neo4j.neo4j_uri = val

    @property
    def neo4j_user(self):
        return getattr(self.neo4j, 'neo4j_user', None)

    @neo4j_user.setter
    def neo4j_user(self, val):
        if self.neo4j:
            self.neo4j.neo4j_user = val

    @property
    def neo4j_password(self):
        return getattr(self.neo4j, 'neo4j_password', None)

    @neo4j_password.setter
    def neo4j_password(self, val):
        if self.neo4j:
            self.neo4j.neo4j_password = val

    @property
    def _neo4j_reconnect_attempts(self):
        return getattr(self.neo4j, '_neo4j_reconnect_attempts', 0)

    @property
    def _neo4j_reconnect_task(self):
        return getattr(self.neo4j, '_neo4j_reconnect_task', None)

    @property
    def _neo4j_auth_error(self):
        return getattr(self.neo4j, '_neo4j_auth_error', False)

    async def close(self):
        """Close all stores."""
        if self.redis:
            await self.redis.close()
        if self.neo4j:
            await self.neo4j.close()

    async def trigger_reconnect(self, force: bool = False) -> dict:
        """Proxy to Neo4j trigger reconnect to expose admin command."""
        if not self.neo4j:
            return {"started": False, "message": "Neo4j store not configured"}
        return await self.neo4j.trigger_reconnect(force=force)

    # Delegate Redis methods
    async def get_active_context(self, session_id: str) -> str:
        if self.redis:
            return await self.redis.get_active_context(session_id)
        return ""  # Return empty string when Redis is not available

    async def save_active_context(self, session_id: str, context: str):
        if self.redis:
            await self.redis.save_active_context(session_id, context)
        # Silently fail when Redis is not available

    async def touch_session(self, session_id: str):
        """Mark session as active by updating last_active timestamp in Redis without changing the active context."""
        try:
            if self.redis and self.redis.redis:
                import time
                await self.redis.redis.set(f"session:{session_id}:last_active_at", int(time.time()), ex=settings.redis_ttl)
        except Exception:
            # Not critical; ignore failures
            pass

    async def clear_session_context(self, session_id: str):
        """Clear the active (hot) context for a session."""
        if self.redis:
            await self.redis.clear_session(session_id)

    # Delegate Neo4j methods
    async def add_memory(self, session_id: Optional[str] = None, content: str = "", category: Optional[str] = None, tags: Optional[List[str]] = None, importance: int = 5, metadata: Optional[Dict[str, Any]] = None, llm_client=None):
        # 0. Preliminary cleaning & hygiene checks
        raw_content = content or ''
        # Skip JSON dump / HTML noisy content unless it contains technical signals
        if is_json_like(raw_content) and not has_technical_signal(raw_content):
            logger.warning('Skipping add_memory: json-like content without technical signal')
            return None
        if is_html_like(raw_content) and not has_technical_signal(raw_content):
            logger.warning('Skipping add_memory: html-like content without technical signal')
            return None

        # Compute cleaned content and detect technical signal
        tech_signal = has_technical_signal(raw_content)
        content_cleaned = clean_content(raw_content, remove_emojis=not tech_signal, remove_non_ascii=False, annotate_technical=tech_signal)
        tech_signal = has_technical_signal(raw_content)
        if not tech_signal and (not content_cleaned or len(content_cleaned) < 20):
            logger.warning('Skipping add_memory: content empty or too short after cleaning')
            return None

        # Compute a content hash for dedup (based on cleaned content to avoid duplicate noisy entries)
        content_hash = hashlib.sha256((content_cleaned or '').encode('utf-8')).hexdigest()

        # 1. Distill entities (Graph Wiring)
        entities = []
        try:
            # Use provided llm_client or self.llm_client
            client = llm_client or self.llm_client
            if client and content_cleaned:
                distilled = await distill_moment(content_cleaned, llm_client=client, metadata=metadata)
                if isinstance(distilled, dict):
                    entities = distilled.get("entities", [])
        except Exception as e:
            logger.warning(f"Failed to distill entities: {e}")

        # 2. Add to Neo4j (Graph + Document)
        # Pass cleaned content and additional properties to Neo4j
        # Tag technical content
        if tech_signal:
            tags = tags or []
            if 'technical' not in tags and '#technical' not in tags:
                tags.append('#technical')

        memory_id = await self.neo4j.add_memory(session_id, content, category, tags, importance, metadata, entities=entities, content_cleaned=content_cleaned, content_hash=content_hash, content_embedding_text=content_cleaned if not tech_signal else content_cleaned)
        
        # 3. Vector Indexing (Semantic Search)
        if self.vector_adapter and self._vector_enabled and memory_id and content_cleaned:
            try:
                client = llm_client or self.llm_client
                if client:
                    # Generate embedding
                    embeddings = await client.get_embeddings(content_cleaned)
                    if embeddings and len(embeddings) > 0:
                        # Handle list of lists or single list
                        embedding = embeddings[0] if isinstance(embeddings[0], list) else embeddings
                        # Index
                        await self.vector_adapter.index_chunk(
                            embedding_id=f"mem:{memory_id}",
                            node_id=memory_id,
                            chunk_index=0,
                            embedding=embedding,
                            metadata={
                                "content": content_cleaned,
                                "category": category,
                                "session_id": session_id,
                                "importance": importance,
                                "created_at": metadata.get("created_at") if metadata else None
                            }
                        )
            except Exception as e:
                logger.warning(f"Failed to index vector: {e}")

        # Return the created memory id
        return memory_id
    async def search_memories(self, query_text: Optional[str] = None, category: Optional[str] = None, tags: Optional[List[str]] = None, limit: int = 10) -> List[Dict[str, Any]]:
        if not query_text:
            # Fallback to recent if no query
            # Note: Neo4jStore needs a get_recent method, adding it to TODO or using direct cypher
            # For now, simple search
            return await self.neo4j.search_memories("", category, limit)
        return await self.neo4j.search_memories(query_text, category, limit)

    async def search_memories_neo4j(self, query_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories specifically in Neo4j (full-text)."""
        return await self.neo4j.search_memories(query_text, None, limit)

    async def get_recent_by_category(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent memories by category."""
        # This requires a new method in Neo4jStore or a direct query here.
        # Adding direct query support via Neo4jStore.execute_cypher would be cleaner,
        # but for now let's add a helper to Neo4jStore or just use search with empty query if supported.
        # Actually, let's implement it properly by delegating to a new method we'll add to Neo4jStore,
        # or using search_memories with empty query if it supports sorting by time.
        # The current search_memories implementation in Neo4jStore sorts by nothing explicit if no query.
        # Let's add a dedicated method to Neo4jStore in a separate step, but for now we can try search.
        # Wait, the error is AttributeError on TieredMemory, so we MUST define it here.
        return await self.neo4j.get_recent_by_category(category, limit)

    async def get_summaries(self, session_id: str, limit: int = 5) -> List[str]:
        """Get recent summaries."""
        # Delegate to Neo4jStore
        return await self.neo4j.get_summaries(session_id, limit)

    async def save_summary(self, session_id: str, summary: str):
        """Save a conversation summary."""
        await self.neo4j.add_memory(
            session_id=session_id,
            content=summary,
            category="summary",
            tags=["summary"],
            importance=3,
            metadata={}
        )

    async def flush_to_neo4j(self, session_id: str, summary: str, original_tokens: int):
        """Flush summary to Neo4j."""
        await self.neo4j.add_memory(
            session_id=session_id,
            content=summary,
            category="summary",
            tags=["summary", "auto-flush"],
            importance=3,
            metadata={"original_token_count": original_tokens}
        )

    def count_tokens(self, text: str) -> int:
        if not text: return 0
        try: return len(self.tokenizer.encode(text, disallowed_special=()))
        except: return len(text) // 4
