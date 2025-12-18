from neo4j import GraphDatabase
import sys

uri = "bolt://localhost:7687"
user = "neo4j"
password = "password"

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        # Count all Memory nodes
        result = session.run("MATCH (n:Memory) RETURN count(n) as count")
        total_memory = result.single()["count"]
        print(f"Total Memory nodes: {total_memory}")

        # Count summary nodes
        result = session.run("MATCH (n:Memory) WHERE n.category='summary' RETURN count(n) as count")
        total_summaries = result.single()["count"]
        print(f"Total Summary nodes: {total_summaries}")

        # Count unlinked summaries (what MemoryWeaver looks for)
        result = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() RETURN count(s) as count")
        unlinked_summaries = result.single()["count"]
        print(f"Unlinked Summary nodes: {unlinked_summaries}")

        # Check for any recent Memory nodes (last 24 hours)
        result = session.run("""
            MATCH (n:Memory) 
            WHERE datetime(n.created_at) > datetime() - duration('P1D')
            RETURN count(n) as count
        """)
        recent_memory = result.single()["count"]
        print(f"Memory nodes created in last 24h: {recent_memory}")

    driver.close()
except Exception as e:
    print(f"Error connecting to Neo4j: {e}")
