import os
import pytest
from data_pipeline.import_turns_neo4j import TurnImporterNeo4j
from dataclasses import dataclass


@dataclass
class Turn:
    session_id: str
    turn_num: int
    timestamp: str | None
    speaker: str
    content: str
from utils.neo4j_embedded import EmbeddedNeo4j


def test_import_turns_neo4j_skip_when_no_neo4j():
    # If Neo4j not available, this test skips (for local runs without docker)
    if os.getenv("ECE_USE_DOCKER", "0") != "1":
        pytest.skip("Skipping Neo4j integration test (ECE_USE_DOCKER!=1)")

    # Prefer an already-running Neo4j container, otherwise fall back to embedded
    import socket
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    bolt_host = "localhost"
    bolt_port = 7687
    if os.getenv("NEO4J_URI"):
        # If provided via env, use it
        neo4j_uri = os.getenv("NEO4J_URI")

    def _is_port_open(host, port, timeout=1):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    embedded = None
    if _is_port_open(bolt_host, bolt_port):
        # External Neo4j is running from docker-compose
        importer = TurnImporterNeo4j(bolt_uri=neo4j_uri)
    else:
        # Try to start embedded Neo4j
        neo4j = EmbeddedNeo4j()
        started = neo4j.start()
        assert started, "Neo4j did not start"
        importer = TurnImporterNeo4j(bolt_uri=neo4j.get_bolt_uri())

    # Create a couple of fake turns
    t1 = Turn(session_id="s1", turn_num=1, timestamp=None, speaker="user", content="Hello world")
    t2 = Turn(session_id="s1", turn_num=2, timestamp=None, speaker="assistant", content="Hi there")

    try:
        importer.import_turns([t1, t2])
    finally:
        importer.close()
        # Only stop embedded (if we started one)
        try:
            if 'neo4j' in locals() and isinstance(neo4j, EmbeddedNeo4j) and neo4j.is_running():
                neo4j.stop()
        except Exception:
            pass
