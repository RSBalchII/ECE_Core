from neo4j import GraphDatabase
from src.config import Settings


def run_checks():
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return

    uri = s.neo4j_uri
    user = s.neo4j_user
    password = s.neo4j_password

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # Count Memory nodes
        count_mem = session.run('MATCH (m:Memory) RETURN count(m) AS c').single().value()
        print('Memory nodes:', count_mem)

        # Search for 'Sybil' in Memory content (case-insensitive)
        term = 'sybil'
        results = session.run(
            """
            MATCH (m:Memory)
            WHERE toLower(m.content) CONTAINS $term
            RETURN m.content AS content, m.created_at AS created_at
            LIMIT 5
            """,
            term=term
        )
        rows = list(results)
        print('Memory rows containing sybil:', len(rows))
        for r in rows:
            c = r['content'] or ''
            print('-', c[:200].replace('\n', ' '))

        # Check Entity node (case-insensitive match against name or display_name)
        name = 'Sybil'
        ent_rec = session.run(
            """
            MATCH (e:Entity)
            WHERE toLower(e.name) = toLower($name)
               OR (e.display_name IS NOT NULL AND toLower(e.display_name) = toLower($name))
            RETURN e, COALESCE(e.display_name, e.name) AS display_name, e.mention_count AS mention_count
            LIMIT 1
            """,
            name=name
        ).single()

        print('Entity Sybil found:', bool(ent_rec))
        if ent_rec:
            print('display_name:', ent_rec['display_name'], 'mention_count:', ent_rec['mention_count'])

        # Count MENTIONS relationships to the matched entity
        mentions = session.run(
            """
            MATCH (e:Entity)
            WHERE toLower(e.name) = toLower($name)
               OR (e.display_name IS NOT NULL AND toLower(e.display_name) = toLower($name))
            MATCH (e)<-[:MENTIONS]-(m:Memory)
            RETURN count(m) AS c
            """,
            name=name
        ).single().value()
        print('Memories mentioning Sybil:', mentions)

        # List indexes
        idx = session.run('SHOW INDEXES').values()
        print('Indexes (name, type, properties):')
        for i in idx:
            print(i)

    driver.close()


if __name__ == '__main__':
    run_checks()
