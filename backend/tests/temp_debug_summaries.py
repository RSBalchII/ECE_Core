from neo4j import GraphDatabase
from src.config import Settings

s = Settings()
if not s.neo4j_enabled:
    print('Neo4j disabled; skipping')
    exit(0)

driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
with driver.session() as session:
    res = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() RETURN elementId(s) as s_eid, s.content as content LIMIT 5")
    rows = list(res)
    for r in rows:
        content = r['content'] or ''
        print('s_eid=', r['s_eid'], 'len=', len(content), 'snippet=', content[:200].replace('\n', ' '))

driver.close()
