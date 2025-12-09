from neo4j import GraphDatabase
from src.config import Settings


def run_fixup():
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return

    uri = s.neo4j_uri
    user = s.neo4j_user
    password = s.neo4j_password

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print('\n== Creating indexes (if not exists) ==\n')
        try:
            session.run("""
            CREATE FULLTEXT INDEX memorySearch IF NOT EXISTS
            FOR (m:Memory) ON EACH [m.content, m.tags]
            """)
            print('Created/ensured fulltext index memorySearch')
        except Exception as e:
            print('Index creation warning/error:', e)

        try:
            session.run("""
            CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)
            """)
            print('Created/ensured index entity_name')
        except Exception as e:
            print('Index creation warning/error:', e)

        print('\n== Normalizing Memory properties ==\n')
        updates = [
            ("Set created_at from timestamp if missing",
             "MATCH (m:Memory) WHERE m.created_at IS NULL AND m.timestamp IS NOT NULL SET m.created_at = m.timestamp RETURN count(m) AS n"),
            ("Set default tags where missing",
             "MATCH (m:Memory) WHERE m.tags IS NULL SET m.tags = '[]' RETURN count(m) AS n"),
            ("Set default importance where missing",
             "MATCH (m:Memory) WHERE m.importance IS NULL SET m.importance = 5 RETURN count(m) AS n"),
            ("Set default category where missing",
             "MATCH (m:Memory) WHERE m.category IS NULL SET m.category = 'conversation' RETURN count(m) AS n"),
            ("Set default metadata where missing",
             "MATCH (m:Memory) WHERE m.metadata IS NULL SET m.metadata = '{}' RETURN count(m) AS n"),
        ]

        from scripts.neo4j.maintenance.neo4j_fixup import *
