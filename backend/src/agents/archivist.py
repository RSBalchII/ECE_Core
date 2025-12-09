"""
Archivist Agent (Maintenance & Curation)
Handles Knowledge Base Freshness, Pruning, and Re-verification.
"""
import logging
import asyncio
from typing import List, Dict, Any, TYPE_CHECKING
from datetime import datetime, timedelta, timezone
if TYPE_CHECKING:
    # Avoid importing heavy deps during test collection (neo4j etc)
    from src.memory import TieredMemory
    from src.agents.verifier import VerifierAgent
else:
    TieredMemory = None  # type: ignore
    VerifierAgent = None  # type: ignore
from src.maintenance.weaver import MemoryWeaver
from src.config import Settings, settings as GLOBAL_SETTINGS

logger = logging.getLogger(__name__)

class ArchivistAgent:
    """
    Archivist Agent manages the health and freshness of the Knowledge Graph.
    It runs background tasks to prune stale nodes and trigger re-verification.
    """
    
    def __init__(self, memory: TieredMemory, verifier: VerifierAgent, settings: Settings | None = None):
        self.memory = memory
        self.verifier = verifier
        self.running = False
        self._task = None
        # Use the provided settings instance or fallback to the module-global settings
        self.settings = settings or GLOBAL_SETTINGS
        self.weaver = MemoryWeaver(self.settings)
        self._last_weave = None
        self._last_purge = None
        
    async def start(self):
        """Start the background maintenance loop."""
        self.running = True
        self._task = asyncio.create_task(self._maintenance_loop())
        logger.info("Archivist Agent started (Maintenance Loop)")

    async def stop(self):
        """Stop the background maintenance loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Archivist Agent stopped")

    async def _maintenance_loop(self):
        """
        Main loop:
        1. Check for stale nodes (Freshness Protocol)
        2. Prune low-value/old nodes
        3. Sleep
        """
        while self.running:
            try:
                logger.info("Archivist: Starting maintenance cycle...")
                # Janitor: purge contaminated nodes if enabled and interval elapsed
                try:
                    if getattr(self.settings, 'archivist_auto_purge_enabled', False):
                        now = datetime.now(timezone.utc)
                        interval = getattr(self.settings, 'archivist_auto_purge_interval_seconds', 600)
                        if not self._last_purge or (now - self._last_purge).total_seconds() >= interval:
                            logger.info("Archivist: Running auto-purge (Janitor) cycle to clean contaminated nodes")
                            try:
                                await self.purge_contaminated_nodes(dry_run=getattr(self.settings, 'archivist_auto_purge_dry_run', True))
                            except Exception as purge_e:
                                logger.error(f"Archivist: Auto-purge failed: {purge_e}")
                            self._last_purge = now
                except Exception as purge_check_e:
                    # Don't let janitor failures stop maintenance loop
                    logger.error(f"Archivist: Janitor pre-check failed: {purge_check_e}")
                await self.check_freshness()

                # Run weaving on short cadence (every 60 minutes) if enabled
                if self.settings.weaver_enabled:
                    now = datetime.now(timezone.utc)
                    # Run every 60 minutes
                    if not self._last_weave or (now - self._last_weave).total_seconds() >= 3600:
                        logger.info("Archivist: Running MemoryWeaver weave_recent (dry-run) as scheduled heartbeat")
                        try:
                            # Use settings defaults; ensure dry-run by default
                            await self.run_weaving_cycle()
                            self._last_weave = now
                        except Exception as weave_e:
                            logger.error(f"Archivist: Weaver run failed: {weave_e}")
                # await self.prune_stale() # Disabled for now to prevent data loss during beta
                logger.info("Archivist: Maintenance cycle complete.")
            except Exception as e:
                logger.error(f"Archivist error: {e}")
            # Run every hour (3600s) - configurable
            await asyncio.sleep(3600)

    
    async def run_weaving_cycle(self, hours: int | None = None, threshold: float | None = None, max_commit: int | None = None, candidate_limit: int | None = None, batch_size: int | None = None, prefer_same_app: bool | None = None, dry_run: bool | None = None, csv_out: str | None = None):
        """
        Trigger a weaving cycle using the MemoryWeaver. Uses Settings defaults if parameters not supplied.
        """
        try:
            # If settings indicate weaving is disabled, skip it
            if not self.settings.weaver_enabled:
                logger.info("Archivist: Weaver disabled in settings; skipping")
                return
            # Resolve commit flag: avoid writes unless explicitly configured
            if dry_run is None:
                dry_run = self.settings.weaver_dry_run_default
            # Run the weave
            candidate_limit = candidate_limit if candidate_limit is not None else getattr(self.settings, 'weaver_candidate_limit', 200)
            batch_size = batch_size if batch_size is not None else getattr(self.settings, 'weaver_batch_size_default', getattr(self.settings, 'llm_embeddings_default_batch_size', 4))
            result = await self.weaver.weave_recent(hours=hours, threshold=threshold, max_commit=max_commit, candidate_limit=candidate_limit, prefer_same_app=prefer_same_app, dry_run=dry_run, csv_out=csv_out, batch_size=batch_size)
            logger.info(f"Archivist: Weaver run completed: {result}")
            return result
        except Exception as e:
            logger.error(f"Archivist: Weaver cycle error: {e}")
            return None

    async def check_freshness(self, limit: int = 10):
        """
        Scan for nodes that need re-verification.
        Criteria: High importance (>7) but old (>30 days) or missing verification.
        """
        # We need a custom Cypher query here.
        # Since we can't easily add methods to Neo4jStore at runtime without editing it,
        # we'll use execute_cypher if available, or add a method to Neo4jStore.
        # Neo4jStore has execute_cypher method.
        
        query = """
        MATCH (m:Memory)
        WHERE m.importance > 7 
          AND (m.last_verified_at IS NULL OR datetime(m.last_verified_at) < datetime($threshold))
        RETURN elementId(m) as id, m.content as content, m.metadata as metadata
        LIMIT $limit
        """
        
        threshold = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        try:
            results = await self.memory.neo4j.execute_cypher(query, {"threshold": threshold, "limit": limit})
            
            for record in results:
                await self.reverify_node(record)
                
        except Exception as e:
            logger.error(f"Freshness check failed: {e}")

    async def reverify_node(self, record: Dict[str, Any]):
        """
        Trigger VerifierAgent to check a node.
        """
        node_id = record.get("id")
        content = record.get("content")
        
        logger.info(f"Archivist: Re-verifying node {node_id}...")
        
        # We need context to verify against. For now, we verify against the node itself 
        # (checking internal consistency) or we could search for related nodes.
        # Ideally, verifier searches for primary sources.
        
        # Search for related context to help verification
        context = await self.memory.search_memories(content[:100], None, limit=5)
        
        verification = await self.verifier.verify_claim(content, context)
        
        # Update node with verification result
        update_query = """
        MATCH (m:Memory) WHERE elementId(m) = $node_id
        SET m.last_verified_at = $now,
            m.freshness_score = $score,
            m.verification_note = $note
        """
        
        await self.memory.neo4j.execute_cypher(update_query, {
            "node_id": node_id,
            "now": datetime.now(timezone.utc).isoformat(),
            "score": verification.get("score", 0.0),
            "note": "Verified by VerifierAgent" if verification.get("verified") else "Verification failed"
        })
        
        logger.info(f"Archivist: Node {node_id} updated with score {verification.get('score')}")

    def _content_contains_marker(self, content: str, markers: list[str]) -> bool:
        """
        Simple helper to check if content or metadata contains any marker.
        Lower-casing helps match markers configured in the settings.
        """
        if not content:
            return False
        content_lower = content.lower()
        for m in markers:
            if m and m.lower() in content_lower:
                return True
        return False

    async def find_contaminated_nodes(self, markers: list[str]) -> list:
        """
        Use the provided markers to identify candidate nodes in Neo4j.
        This returns a list of node records (id, content, metadata, created_at, session_id, category).
        """
        if not markers:
            return []

        results = []
        try:
            q = """
            MATCH (m:Memory)
            WHERE (
                """ + ' OR '.join(["toLower(coalesce(m.content,'') ) CONTAINS $marker_%d" % i for i in range(len(markers))]) + """
            ) OR (
                """ + ' OR '.join(["toLower(coalesce(m.metadata,'') ) CONTAINS $marker_meta_%d" % i for i in range(len(markers))]) + """
            )
            RETURN elementId(m) as id, m.content as content, m.metadata as metadata, m.created_at as created_at, m.session_id as session_id, m.category as category, m.status as status
            """
            params = {}
            for i,m in enumerate(markers):
                params[f"marker_{i}"] = m.lower()
                params[f"marker_meta_{i}"] = m.lower()
            # Neo4j driver session loop
            drv = getattr(self.memory, 'neo4j', None)
            if not drv or not getattr(drv, 'neo4j_driver', None):
                logger.info("Archivist: Neo4j driver not configured; cannot find contaminated nodes")
                return []
            async with drv.neo4j_driver.session() as session:
                result = await session.run(q, params)
                rows = await result.data()
                for r in rows:
                    results.append(r)
        except Exception as e:
            logger.error(f"Archivist: Failed to find contaminated nodes: {e}")
        return results

    async def purge_contaminated_nodes(self, dry_run: bool = True, markers: list[str] | None = None) -> dict:
        """
        Detect nodes that match the configured contamination markers and optionally delete them.
        Safety: only delete nodes that are NOT committed (i.e., m.status != 'committed').
        Returns a dict with counts for found and deleted nodes.
        """
        if markers is None:
            markers = getattr(self.settings, 'archivist_auto_purge_markers', [])
        markers = [m for m in (markers or []) if m]
        if not markers:
            logger.info("Archivist: No markers configured for auto-purge; skipping")
            return {"found": 0, "deleted": 0}

        found = 0
        deleted = 0
        try:
            # Build a safe cypher that matches any content or metadata marker and excludes 'committed' nodes
            conds = []
            params = {}
            for i, m in enumerate(markers):
                params[f"marker_{i}"] = m.lower()
                params[f"marker_meta_{i}"] = m.lower()
                conds.append(f"toLower(coalesce(m.content,'')) CONTAINS $marker_{i}")
                conds.append(f"toLower(coalesce(m.metadata,'')) CONTAINS $marker_meta_{i}")

            if not conds:
                return {"found": 0, "deleted": 0}

            where_clause = '(' + ' OR '.join(conds) + ") AND (m.status IS NULL OR toLower(m.status) <> 'committed')"
            q = f"""
            MATCH (m:Memory)
            WHERE {where_clause}
            RETURN elementId(m) as id, m.content as content, m.metadata as metadata, m.created_at as created_at, m.session_id as session_id, m.category as category
            """
            drv = getattr(self.memory, 'neo4j', None)
            if not drv or not getattr(drv, 'neo4j_driver', None):
                logger.info("Archivist: Neo4j driver not configured; skipping purge")
                return {"found": 0, "deleted": 0}
            async with drv.neo4j_driver.session() as session:
                result = await session.run(q, params)
                rows = await result.data()
                found = len(rows)
                logger.info(f"Archivist-Janitor: Found {found} candidate contaminated nodes")
                if found and not dry_run:
                    for row in rows:
                        try:
                            await session.run('MATCH (m:Memory) WHERE elementId(m) = $id DETACH DELETE m', {'id': row.get('id')})
                            deleted += 1
                        except Exception as e:
                            logger.error(f"Archivist-Janitor: Failed to delete node {row.get('id')}: {e}")
                # if dry_run, list candidates to log
                if dry_run:
                    for row in rows:
                        logger.warning(f"Archivist-Janitor: Dry-run found candidate: id={row.get('id')} session_id={row.get('session_id')} category={row.get('category')} created_at={row.get('created_at')}")
        except Exception as e:
            logger.error(f"Archivist: purge_contaminated_nodes error: {e}")
        logger.info(f"Archivist-Janitor: Purge results: found={found} deleted={deleted} dry_run={dry_run}")
        return {"found": found, "deleted": deleted}

    async def prune_stale(self):
        """
        Prune nodes with low importance (<3) and old age (>90 days).
        """
        query = """
        MATCH (m:Memory)
        WHERE m.importance < 3 
          AND datetime(m.created_at) < datetime($threshold)
        DELETE m
        """
        threshold = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        
        try:
            await self.memory.neo4j.execute_cypher(query, {"threshold": threshold})
            logger.info("Archivist: Pruned stale nodes.")
        except Exception as e:
            logger.error(f"Pruning failed: {e}")
