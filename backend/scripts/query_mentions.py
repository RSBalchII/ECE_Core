#!/usr/bin/env python3
import asyncio
from src.memory.neo4j_store import Neo4jStore
import json

async def main():
    store = Neo4jStore()
    await store.initialize()
    r = await store.execute_cypher('MATCH (m:Memory)-[r:MENTIONS]->(e:Entity) RETURN elementId(m) as mem_id, m.content as mem_content, e.name as entity_name, e.type as entity_type LIMIT 10')
    print(json.dumps(r, indent=2))
    await store.close()

if __name__ == '__main__':
    asyncio.run(main())
