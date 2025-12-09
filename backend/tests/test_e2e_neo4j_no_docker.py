import os
import socket
import time
from neo4j import GraphDatabase
import pytest
from src.utils.neo4j_embedded import EmbeddedNeo4j


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _setup_driver(uri: str, user: str = None, password: str = None):
    auth = (user, password) if user else None
    return GraphDatabase.driver(uri, auth=auth)


@pytest.mark.e2e
@pytest.mark.skip(reason="Flaky in local environment with existing Neo4j")
def test_neo4j_end_to_end_no_docker():
    """End-to-end Neo4j test without Docker.

    Behavior:
    - If a Neo4j Bolt service is running on localhost:7687, use it.
    - Else attempt to start EmbeddedNeo4j with a local distribution.
    - Import sample nodes and relationships, then query for them.
    - Clean up EmbeddedNeo4j if it was started.
    """
    bolt_host = "127.0.0.1"
    bolt_port = 7687
    bolt_uri = os.getenv("NEO4J_URI", f"bolt://{bolt_host}:{bolt_port}")
    neo4j_user = os.getenv("NEO4J_USER", None)
    neo4j_password = os.getenv("NEO4J_PASSWORD", None)

    started_embedded = False
    if not _is_port_open(bolt_host, bolt_port):
        # Attempt to start embedded Neo4j
        e = EmbeddedNeo4j()
        started_embedded = e.start()
        assert started_embedded, "Embedded Neo4j could not be started and no external Neo4j is available"
        bolt_uri = e.get_bolt_uri()

    driver = _setup_driver(bolt_uri, neo4j_user, neo4j_password)

    try:
        with driver.session() as session:
            # Create a test database of simple Memory nodes and sample content
            # If a unique constraint fails due to duplicate nodes, remove duplicates for clean test runs
            try:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE")
            except Exception as create_exc:
                # Attempt to remove duplicate Memory nodes that violate uniqueness
                session.run("MATCH (m:Memory) WHERE m.id IS NOT NULL WITH m.id AS id, collect(m) AS nodes WHERE size(nodes) > 1 UNWIND nodes[1..] AS extra DETACH DELETE extra")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE")
            # Clean up any existing test nodes
            session.run("MATCH (m:Memory {test: true}) DETACH DELETE m")

            # Add nodes
            session.run(
                "CREATE (m:Memory {id: 't1', session_id: 's1', content: 'I love cats and coffee', speaker: 'user', test: true})"
            )
            session.run(
                "CREATE (m:Memory {id: 't2', session_id: 's1', content: 'I love dogs and tea', speaker: 'assistant', test: true})"
            )
            # Create relationship
            session.run("MATCH (a:Memory {id:'t1'}),(b:Memory {id:'t2'}) MERGE (a)-[:NEXT]->(b)")

            # Query for a simple keyword and confirm results
            result = session.run("MATCH (m:Memory {test: true}) WHERE m.content CONTAINS 'cats' RETURN m.id as id, m.content as content")
            records = [r for r in result]
            assert len(records) >= 1
            assert records[0]["id"] == "t1"

            # Sample a random node (simulate sampling behavior) and assert it's one we inserted
            res = session.run("MATCH (m:Memory {test: true}) RETURN m.id ORDER BY rand() LIMIT 1")
            rec = res.single()
            assert rec is not None
            assert rec["m.id"] in ("t1", "t2") or rec["m.id"] in ("t1", "t2")

            # Clean up test nodes
            session.run("MATCH (m:Memory {test: true}) DETACH DELETE m")

    finally:
        driver.close()
        if started_embedded:
            try:
                e.stop()
            except Exception:
                pass
