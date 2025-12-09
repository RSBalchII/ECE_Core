#!/usr/bin/env python3
import asyncio
from src.memory.neo4j_store import Neo4jStore

async def main():
    store = Neo4jStore()
    await store.initialize()
    mem = await store.execute_cypher('MATCH (m:Memory) RETURN count(m) AS c')
    ent = await store.execute_cypher('MATCH (e:Entity) RETURN count(e) AS c')
    mentions = await store.execute_cypher('MATCH (m:Memory)-[r:MENTIONS]->(e:Entity) RETURN count(r) as c')
    distilled = await store.execute_cypher('MATCH (s:Memory)-[r:DISTILLED_FROM]->(o:Memory) RETURN count(r) as c')
    print('Memory count:', mem[0]['c'] if mem else 0)
    print('Entity count:', ent[0]['c'] if ent else 0)
    print('MENTIONS rel count:', mentions[0]['c'] if mentions else 0)
    print('DISTILLED_FROM rel count:', distilled[0]['c'] if distilled else 0)
    await store.close()

if __name__ == '__main__':
    asyncio.run(main())
