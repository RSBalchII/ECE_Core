from neo4j import GraphDatabase
from src.config import Settings

def run_check():
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    with driver.session() as session:
        missing_count = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() RETURN count(s) as c").single().value()
        missing_with_meta = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() AND s.metadata IS NOT NULL AND s.metadata CONTAINS 'distilled_from' RETURN count(s) as c").single().value()
        missing_no_meta = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() AND (s.metadata IS NULL OR NOT s.metadata CONTAINS 'distilled_from') RETURN count(s) as c").single().value()
        print(f"Missing total: {missing_count}")
        print(f"Missing with metadata 'distilled_from': {missing_with_meta}")
        print(f"Missing with no metadata or no 'distilled_from': {missing_no_meta}")
        rows = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() RETURN elementId(s) as s_eid, s.metadata as metadata LIMIT 20")
        print('\nSamples of missing summary nodes:')
        for r in rows:
            print(r)
    driver.close()

if __name__ == '__main__':
    run_check()
