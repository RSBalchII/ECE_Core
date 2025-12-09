#!/usr/bin/env python3
"""
Query how many Memory nodes are missing 'app_id' and list sample.
"""
import asyncio
from src.memory.neo4j_store import Neo4jStore

async def main():
    store = Neo4jStore()
    await store.initialize()
    if not store.neo4j_driver:
        print('Neo4j not connected')
        return
    q = "MATCH (m:Memory) WHERE m.app_id IS NULL OR m.app_id = '' RETURN count(m) as cnt LIMIT 1"
    res = await store.execute_cypher(q)
    print('Missing app_id count:', res[0].get('cnt') if res else 0)
    q2 = "MATCH (m:Memory) WHERE m.app_id IS NULL OR m.app_id = '' RETURN elementId(m) as eid, m.metadata as metadata LIMIT 20"
    res2 = await store.execute_cypher(q2)
    print('Sample:')
    for r in res2:
        print(r)
    await store.close()

if __name__ == '__main__':
    asyncio.run(main())
