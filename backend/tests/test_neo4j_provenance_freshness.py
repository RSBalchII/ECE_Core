import asyncio
import importlib
import os
# Clear or scope ECE-related environment variables that may cause Settings validation errors during test-run
for _k in list(os.environ.keys()):
    low = _k.lower()
    if 'llm' in low or 'weaver' in low or 'neo4j' in low or 'llama' in low or 'weaver' in low:
        try:
            del os.environ[_k]
        except KeyError:
            pass

from src.utils.neo4j_embedded import EmbeddedNeo4j
# Reload config to ensure changed environment is respected
import src.config
importlib.reload(src.config)
from src.memory.manager import TieredMemory
import hashlib
import pytest


@pytest.mark.asyncio
async def test_add_memory_sets_provenance_and_freshness():
    neo4j = EmbeddedNeo4j()
    assert neo4j.start(), "Embedded Neo4j must start"

    tm = TieredMemory()
    await tm.initialize()

    # Create a content sample with category code
    content = "def hello_world():\n    print(\"hello\")\n"
    content_cleaned = content
    content_hash = hashlib.sha256(content_cleaned.encode('utf-8')).hexdigest()

    metadata = {"source": "src/main.py", "source_type": "code"}
    mem_id = await tm.add_memory(session_id="test", content=content, category="code", tags=["test"], importance=5, metadata=metadata)
    assert mem_id is not None, "Memory creation should return id"

    # Query Neo4j directly via store to confirm fields
    res = await tm.neo4j.execute_cypher("MATCH (m:Memory) WHERE m.content_hash = $content_hash RETURN m.provenance_score as ps, m.freshness_score as fs, m.last_verified_at as lv", {"content_hash": content_hash})
    assert res and len(res) > 0
    row = res[0]
    assert row.get('ps') is not None, "Provenance score should be set"
    assert float(row.get('fs')) == pytest.approx(1.0)
    # last_verified_at should be None for newly created memory without explicit verification
    assert row.get('lv') is None

    # Clean up
    await tm.close()
    neo4j.stop()
