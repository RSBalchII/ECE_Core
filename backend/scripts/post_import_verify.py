from neo4j import GraphDatabase
from src.config import Settings


def run_report():
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return

    uri = s.neo4j_uri
    user = s.neo4j_user
    password = s.neo4j_password

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        total_mem = session.run('MATCH (m:Memory) RETURN count(m) as c').single().value()
        total_summary_by_cat = session.run("MATCH (s:Memory) WHERE s.category = 'summary' RETURN count(s) as c").single().value()
        total_summary_by_tags = session.run("MATCH (s:Memory) WHERE 'summary' in s.tags OR 'distilled' in s.tags RETURN count(s) as c").single().value()
        total_distilled_relationships = session.run('MATCH (s:Memory)-[:DISTILLED_FROM]->(m:Memory) RETURN count(s) as c').single().value()

        # sample of summary -> original
        sample_rel = session.run(
            "MATCH (s:Memory)-[:DISTILLED_FROM]->(m:Memory) RETURN s.id as summary_id, m.id as original_id, s.content as summary_content LIMIT 10"
        ).values()

        print(f"Total Memory nodes: {total_mem}")
        print(f"Total summary nodes (category='summary'): {total_summary_by_cat}")
        print(f"Total summary nodes (tags include 'summary' or 'distilled'): {total_summary_by_tags}")
        print(f"Total DISTILLED_FROM relationships (count of summary nodes with a relationship): {total_distilled_relationships}")
        print('\nSample summary -> original pairs:')
        for row in sample_rel:
            print(row)

    driver.close()


if __name__ == '__main__':
    run_report()
