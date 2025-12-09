import os
import socket
import time
import json
import pytest
import pytest_asyncio
from src.memory import TieredMemory


def _wait_for_port(host: str, port: int, timeout: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except Exception:
            time.sleep(0.5)
    return False


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("ECE_USE_DOCKER", "0") != "1", reason="Requires docker compose/NEO4J container")
async def test_tieredmemory_add_and_search_neo4j():
    bolt_host = "127.0.0.1"
    bolt_port = 7687
    assert _wait_for_port(bolt_host, bolt_port, timeout=60), "Neo4j Bolt port not available"

    mem = TieredMemory()
    await mem.initialize()
    assert mem.neo4j_driver is not None, "Neo4j driver not initialized"

    # Clean DB
    async with mem.neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")

    # Add two memories
    await mem.add_memory(session_id="s-e2e", content="Hello there Neo4j", category="note", tags=["greeting"], importance=8, metadata={"src": "e2e-test"})
    await mem.add_memory(session_id="s-e2e", content="Some other content for test", category="note", tags=["other"], importance=3, metadata={"src": "e2e-test"})

    # Search by content
    results = await mem.search_memories("Hello")
    assert isinstance(results, list)
    assert len(results) >= 1
    r = results[0]
    assert "memory_id" in r
    assert "content" in r and "Hello there Neo4j" in r["content"]
    assert "score" in r
    assert isinstance(r.get("tags"), list)
    assert "greeting" in r.get("tags", [])
    assert isinstance(r.get("metadata"), dict)
    assert r.get("metadata", {}).get("src") == "e2e-test"

    # Search by category
    results_c = await mem.search_memories(query_text=None, category="note")
    assert isinstance(results_c, list)
    assert len(results_c) >= 2

    # Search by tags
    results_t = await mem.search_memories(query_text=None, tags=["greeting"])  # tag search path
    assert isinstance(results_t, list)
    assert any("Hello there Neo4j" in x["content"] for x in results_t)
    # Validate scoring and metadata shape for tag search result
    tr = results_t[0]
    assert "score" in tr and isinstance(tr["score"], float)
    assert tr.get("metadata", {}).get("src") == "e2e-test"

    await mem.close()
