from src.config import settings
from neo4j import GraphDatabase

print('URI', settings.neo4j_uri)

driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
with driver.session() as session:
    constraints = session.run('SHOW CONSTRAINTS').data()
    print('Constraints:')
    for c in constraints:
        print(c)
    indexes = session.run('SHOW INDEXES').data()
    print('Indexes:')
    for i in indexes:
        print(i)

driver.close()
