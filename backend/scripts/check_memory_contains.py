from src.config import settings
from neo4j import GraphDatabase

driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
with driver.session() as session:
    res = session.run("MATCH (m:Memory) WHERE m.content CONTAINS 'Sybil' RETURN elementId(m) as id, m.content as content LIMIT 10").data()
    print('Result:', res)

driver.close()
