"""Test helper utilities for seeding and cleaning test data in Neo4j.

Functions here are used by e2e tests to create deterministic data (tagged with `test: true`) so
they can be seeded and cleaned between test runs.
"""
from neo4j import GraphDatabase
from typing import List
import os


def _get_driver():
    bolt_host = os.getenv("NEO4J_HOST", "127.0.0.1")
    bolt_port = os.getenv("NEO4J_PORT", "7687")
    bolt_uri = os.getenv("NEO4J_URI", f"bolt://{bolt_host}:{bolt_port}")
    neo4j_user = os.getenv("NEO4J_USER", None)
    neo4j_password = os.getenv("NEO4J_PASSWORD", None)
    auth = (neo4j_user, neo4j_password) if neo4j_user else None
    return GraphDatabase.driver(bolt_uri, auth=auth) if bolt_uri else None


def seed_coda_nodes(count: int = 5, content_prefix: str = "Coda test memory") -> List[str]:
    """Seed `count` Coda Memory nodes and return list of elementId strings.
    Nodes are tagged with `test: true` to allow cleanup.
    """
    driver = _get_driver()
    ids = []
    if not driver:
        return ids
    with driver.session() as session:
        for i in range(count):
            content = f"{content_prefix} #{i+1}"
            result = session.run(
                "CREATE (m:Memory {content: $content, category: 'coda', tags: ['coda'], session_id: 'test', test: true}) RETURN elementId(m) as id",
                {"content": content}
            )
            rec = result.single()
            if rec:
                ids.append(str(rec["id"]))
    driver.close()
    return ids


def clear_test_nodes():
    """Remove nodes created with `test: true` flag."""
    driver = _get_driver()
    if not driver:
        return
    with driver.session() as session:
        session.run("MATCH (m) WHERE m.test = true DETACH DELETE m")
    driver.close()
