from src.config import settings
from neo4j import GraphDatabase

print('URI', settings.neo4j_uri, 'USER', settings.neo4j_user)

try:
    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    with driver.session() as session:
        c = session.run('MATCH (m:Memory) RETURN count(m) as c').single()
        print('Memory count:', c['c'] if c else 0)
        res = session.run('MATCH (m:Memory) RETURN m LIMIT 10').data()
        print('Sample nodes:')
        for r in res:
            print(r)
    driver.close()
except Exception as e:
    print('Error:', e)
