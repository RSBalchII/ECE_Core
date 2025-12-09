import pytest
from src.memory import TieredMemory


class FakeResult:
    def __init__(self, records):
        self._records = records
    async def data(self):
        return self._records
    async def __aiter__(self):
        # Provide async iterator interface like Neo4j AsyncResult
        for r in self._records:
            yield r


class FakeSession:
    def __init__(self, records):
        self._records = records
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def run(self, query, params=None):
        # Return records consistent with fulltext: id, m, score
        return FakeResult(self._records)


class FakeDriver:
    def __init__(self, records):
        self._records = records
    def session(self):
        return FakeSession(self._records)


@pytest.mark.asyncio
async def test_search_memories_fulltext_score_present():
    mem = TieredMemory()
    # Create a fake fulltext record with score
    record = {"id": 123, "m": {"content": "Sybil is a sample memory", "tags": [], "importance": 7, "created_at": "2025-01-01T00:00:00Z"}, "score": 0.9}
    # Use the backward-compatible property for tests that set `neo4j_driver` on the TieredMemory
    mem.neo4j_driver = FakeDriver([record])
    results = await mem.search_memories("Sybil", limit=5)
    assert isinstance(results, list)
    assert len(results) >= 1
    r = results[0]
    assert "score" in r
    assert isinstance(r["score"], float)
    assert 0.0 <= r["score"] <= 1.0
