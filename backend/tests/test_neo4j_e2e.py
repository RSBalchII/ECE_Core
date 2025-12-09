"""
Neo4j end-to-end tests

These tests require a running Neo4j server and should be run with
ECE_USE_DOCKER=1 so the `conftest` fixture brings up the compose stack.
"""
import os
import socket
import time
import pytest
from neo4j import GraphDatabase


def _wait_for_port(host: str, port: int, timeout: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except Exception:
            time.sleep(0.5)
    return False


@pytest.mark.skipif(os.getenv("ECE_USE_DOCKER", "0") != "1", reason="Requires docker compose/NEO4J container")
def test_neo4j_basic_import_and_query():
    """Create memory nodes and query them using Cypher to validate basic flow."""
    bolt_host = "127.0.0.1"
    bolt_port = 7687
    assert _wait_for_port(bolt_host, bolt_port, timeout=60), "Neo4j Bolt port not available"

    uri = os.getenv("NEO4J_URI", f"bolt://{bolt_host}:{bolt_port}")
    driver = GraphDatabase.driver(uri, auth=None)

    try:
        with driver.session() as session:
            # Clean database
            session.run("MATCH (n) DETACH DELETE n")

            # Create a few Memory nodes
            session.run("CREATE (a:Memory {session_id: 's-1', turn_num: 1, content: 'Hello world'})")
            session.run("CREATE (b:Memory {session_id: 's-1', turn_num: 2, content: 'Follow-up content'})")
            session.run("CREATE (c:Memory {session_id: 's-2', turn_num: 1, content: 'Other session content'})")

            # Create relationships
            session.run("MATCH (a:Memory {session_id: 's-1', turn_num: 1}),(b:Memory {session_id: 's-1', turn_num: 2}) CREATE (a)-[:NEXT]->(b)")

            # Basic query: find content containing 'Hello'
            result = session.run("MATCH (m:Memory) WHERE toLower(m.content) CONTAINS 'hello' RETURN m.session_id AS sid, m.turn_num AS tnum, m.content AS content")
            rows = list(result)
            assert len(rows) == 1
            assert rows[0]["sid"] == "s-1"
            assert rows[0]["tnum"] == 1

            # Relationship query: check NEXT relationship exists
            rel_result = session.run("MATCH (a:Memory {session_id: 's-1', turn_num: 1})-[r:NEXT]->(b:Memory {session_id: 's-1', turn_num: 2}) RETURN count(r) AS c")
            rel_count = rel_result.single()["c"]
            assert rel_count == 1

    finally:
        driver.close()
