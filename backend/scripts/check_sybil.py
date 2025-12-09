from src.config import Settings
from neo4j import GraphDatabase

s = Settings()
if not s.neo4j_enabled:
    print('Neo4j disabled')
    raise SystemExit(1)

driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
with driver.session() as session:
    name = 'sybil'
    # Use `IS NOT NULL` as `exists()` is deprecated in Neo4j 5
    r = session.run(
        """
        MATCH (e:Entity)
        WHERE toLower(e.name) = toLower($name)
           OR (e.display_name IS NOT NULL AND toLower(e.display_name) = toLower($name))
        RETURN COALESCE(e.display_name, e.name) AS dn, e.mention_count AS c
        LIMIT 1
        """,
        name=name
    ).single()

    print('entity sybil found:', bool(r))
    if r:
        print('display_name:', r['dn'], 'mention_count:', r['c'])

    m = session.run(
        """
        MATCH (e:Entity)
        WHERE toLower(e.name) = toLower($name)
           OR (e.display_name IS NOT NULL AND toLower(e.display_name) = toLower($name))
        MATCH (e)<-[:MENTIONS]-(m:Memory)
        RETURN count(m) AS c
        """,
        name=name
    ).single()
    print('mentions relationships:', m['c'] if m else 0)

driver.close()
