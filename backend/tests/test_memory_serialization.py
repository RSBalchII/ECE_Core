import pytest
import asyncio
import sys
from pathlib import Path

# Ensure local modules import in tests
sys.path.insert(0, str(Path(__file__).parent.parent))
from datetime import datetime
from unittest.mock import AsyncMock

from src.memory import TieredMemory


class _FakeSession:
    def __init__(self):
        self.runs = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, cypher, params=None):
        self.runs.append((cypher, params))
        return AsyncMock()


class _FakeDriver:
    def __init__(self):
        self.session_obj = _FakeSession()

    def session(self):
        # return an async context manager
        return self.session_obj


@pytest.mark.asyncio
async def test_add_memory_serializes_metadata_and_tags():
    mem = TieredMemory()
    mem.neo4j_driver = _FakeDriver()

    metadata = {"created": datetime(2025, 11, 13, 0, 0, 0)}
    tags = ["unit", "test"]

    await mem.add_memory(session_id="test", content="Testing metadata", category="unit-test", tags=tags, importance=4, metadata=metadata)

    # Inspect the run parameters recorded
    session = mem.neo4j_driver.session_obj
    assert len(session.runs) == 1
    cypher, params = session.runs[0]
    assert "CREATE (m:Memory" in cypher
    assert params["session_id"] == "test"
    assert params["content"] == "Testing metadata"
    # tags should be list
    assert isinstance(params["tags"], list)
    assert "unit" in params["tags"]
    # metadata should be serialized to string
    assert isinstance(params["metadata"], str)
    assert "2025-11-13" in params["metadata"]


@pytest.mark.asyncio
async def test_search_memories_tags_query_params():
    mem = TieredMemory()
    mem.neo4j_driver = _FakeDriver()

    tags = ["alpha", "beta"]
    # call tag-based search
    await mem.search_memories(query_text=None, category=None, tags=tags, limit=5)
    session = mem.neo4j_driver.session_obj
    assert len(session.runs) == 1
    cypher, params = session.runs[0]
    assert "ANY(t IN m.tags WHERE t IN $tags)" in cypher
    assert params["tags"] == tags
    assert params["limit"] == 5
