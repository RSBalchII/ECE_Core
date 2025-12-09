from neo4j import GraphDatabase
from src.config import Settings

s = Settings()
driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
with driver.session() as session:
    rels = session.run('CALL db.relationshipTypes()').values()
    print('Relationship types:', [r[0] for r in rels])

driver.close()
