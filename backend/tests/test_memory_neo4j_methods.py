import pytest
from src.memory import TieredMemory


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    async def data(self):
        return self._rows


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, query, params=None):
        # Return rows that match the get_summaries query
        if "MATCH (s:Summary" in query:
            return FakeResult([{"summary": "S1", "original_tokens": 10, "compressed_tokens": 2, "created_at": "2025-01-01T00:00:00Z"}])
        # match memory recent query
        return FakeResult([])


class FakeDriver:
    def session(self):
        return FakeSession()


@pytest.mark.asyncio
async def test_get_summaries_parses_results():
    tm = TieredMemory()
    tm.neo4j_driver = FakeDriver()
    res = await tm.get_summaries("s1", limit=2)
    assert isinstance(res, list)
    assert res and res[0]["summary"] == "S1"

@pytest.mark.asyncio
async def test_get_recent_by_category_returns_memories():
    # fake session returns empty, so expects empty list
    tm = TieredMemory()
    tm.neo4j_driver = FakeDriver()
    recent = await tm.get_recent_by_category("event", limit=2)
    assert isinstance(recent, list)
