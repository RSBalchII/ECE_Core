"""Index Neo4j Memory nodes into the vector DB.

This script iterates 'Memory' nodes in Neo4j, computes embeddings via LLMClient,
and indexes them into the configured vector adapter (RedisVectorAdapter by default).

Usage:
  - python scripts/neo4j/indexing/neo4j_index_embeddings.py --limit 100 --dry-run
"""
import asyncio
import argparse
import logging
from src.config import settings
from src.memory import TieredMemory
from src.llm import LLMClient

logger = logging.getLogger("neo4j_index_embeddings")


async def run(limit: int = 100, dry_run: bool = True):
    mem = TieredMemory()
    await mem.initialize()
    llm = LLMClient()

    # We'll page through memories using get_recent_memories_neo4j
    cursor = 0
    page_size = min(limit, 100)
    count = 0
    while True:
        results = await mem.get_recent_memories_neo4j(limit=page_size)
        if not results:
            break
        for r in results:
            content = r.get("content")
            if not content:
                continue
            if dry_run:
                logger.info(f"Would index node {r.get('id')} content len={len(content)}")
                count += 1
                if count >= limit:
                    return
            else:
                try:
                    embeddings = await llm.get_embeddings(content)
                    if embeddings and len(embeddings) > 0:
                        await mem.index_embedding_for_memory(r.get("session_id") or "default", embeddings[0], metadata={"source": "neo4j_import", "node_id": r.get('id')})
                        logger.info(f"Indexed node {r.get('id')} into vector DB")
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to embed/index node {r.get('id')}: {e}")
                if count >= limit:
                    return
        if len(results) < page_size:
            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="Limit how many items to index")
    parser.add_argument("--dry-run", action="store_true", help="Do not index, only log actions")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
