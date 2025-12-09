import sys
import asyncio
sys.path.insert(0, r'C:\Users\rsbiiw\Projects\ECE_Core')
from src.memory.neo4j_store import Neo4jStore

async def main():
    store = Neo4jStore()
    await store.initialize()

    print('Running Neo4jStore.search_memories("Sybil")')
    results = await store.search_memories('Sybil', None, 10)
    print('Search returned:', len(results))
    for r in results[:5]:
        print('-', r.get('content')[:200].replace('\n', ' '), 'score=', r.get('score'))

    # Run the raw cypher fulltext query
    raw_query = """
    CALL db.index.fulltext.queryNodes('memorySearch', $query) YIELD node, score
    RETURN elementId(node) as id, node as m, score
    ORDER BY score DESC
    LIMIT $limit
    """
    print('\nRunning raw cypher fulltext query')
    raw = await store.execute_cypher(raw_query, {'query': 'Sybil', 'limit': 10})
    print('Raw records:', len(raw))
    for r in raw[:5]:
        print('-', (r.get('m', {}).get('content') or '')[:200].replace('\n', ' '), 'score=', r.get('score'))

    # Check how many nodes were added by the direct importer (metadata contains direct_import)
    print('\nCounting nodes added by direct_import metadata...')
    cnt_q = "MATCH (m:Memory) WHERE m.metadata CONTAINS '" + '"source": "direct_import"' + "' RETURN count(m) as cnt"
    print('Counting query:', cnt_q)
    cnt_res = await store.execute_cypher(cnt_q)
    cnt_val = cnt_res[0].get('cnt') if cnt_res else 0
    print('direct_import count:', cnt_val)

    print('\nSample metadata for the first few direct_import nodes:')
    sample_q = "MATCH (m:Memory) WHERE m.metadata CONTAINS '" + '"source": "direct_import"' + "' RETURN m.metadata as md LIMIT 5"
    sample_res = await store.execute_cypher(sample_q)
    for s in sample_res:
        print('- metadata:', s.get('md'))

    await store.close()

if __name__ == '__main__':
    asyncio.run(main())
