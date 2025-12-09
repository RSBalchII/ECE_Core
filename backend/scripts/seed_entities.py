from neo4j import GraphDatabase
from src.config import settings

uri = settings.neo4j_uri
user = settings.neo4j_user
pw = settings.neo4j_password

driver = GraphDatabase.driver(uri, auth=(user, pw))

with driver.session() as session:
    # Create an entity Sybil
    session.run("MERGE (e:Entity {name: $name}) SET e.display_name = $display, e.mention_count = coalesce(e.mention_count, 0)", name='Sybil', display='Sybil')
    # Create a memory mentioning Sybil
    session.run("CREATE (m:Memory {session_id: 'import', content: $content, category: 'event', tags: $tags, importance: 8, created_at: $created_at})", content='Introduced Sybil at the party, Sybil was the speaker and mentioned the plan.', tags=['event','person'], created_at='2025-11-23T18:00:00Z')
    # Link Memory to Entity
    session.run("MATCH (e:Entity {name: $name}) MATCH (m:Memory {session_id: 'import'}) MERGE (e)<-[:MENTIONS]-(m)", name='Sybil')

print('Seeded Sybil entity and associated memory.')

driver.close()
