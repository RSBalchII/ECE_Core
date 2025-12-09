#!/usr/bin/env python3
import asyncio
import json
from src.memory.neo4j_store import Neo4jStore

async def main():
    store = Neo4jStore()
    await store.initialize()
    r = await store.execute_cypher('MATCH (m:Memory) WHERE m.content CONTAINS "Sybil" RETURN elementId(m) as id, m.content as content, m.tags as tags, m.metadata as metadata LIMIT 10')
    print(json.dumps(r, indent=2))
    await store.close()

if __name__ == '__main__':
    asyncio.run(main())
