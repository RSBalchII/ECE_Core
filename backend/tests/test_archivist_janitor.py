import asyncio
import pytest
from datetime import datetime, timezone

from src.agents.archivist import ArchivistAgent
from src.config import Settings


class FakeSessionResult:
    def __init__(self, rows):
        self._rows = rows

    async def data(self):
        return self._rows


class FakeSession:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, q, params=None):
        return FakeSessionResult(self.rows)


class FakeDriver:
    def __init__(self, rows=None):
        self.rows = rows or []

    def session(self):
        return FakeSession(self.rows)


class FakeNeo4jStore:
    def __init__(self, rows=None):
        self.neo4j_driver = FakeDriver(rows)


class FakeMemory:
    def __init__(self, rows=None):
        self.neo4j = FakeNeo4jStore(rows)


class FakeVerifier:
    pass


@pytest.mark.asyncio
async def test_content_contains_marker_true():
    agent = ArchivistAgent(memory=None, verifier=FakeVerifier(), settings=Settings())
    markers = ["thinking_content", "(anchor) ps"]
    assert agent._content_contains_marker("This contains thinking_content: foo", markers)
    assert agent._content_contains_marker("(ANCHOR) PS C:\\Users\\foo> something", markers)


@pytest.mark.asyncio
async def test_content_contains_marker_false():
    agent = ArchivistAgent(memory=None, verifier=FakeVerifier(), settings=Settings())
    markers = ["thinking_content", "(anchor) ps"]
    assert not agent._content_contains_marker("This is a regular human memory", markers)

    @pytest.mark.asyncio
    async def test_markers_detect_various():
        agent = ArchivistAgent(memory=None, verifier=FakeVerifier(), settings=Settings())
        markers = ["thinking_content", "(anchor) ps", "[planner]", "--- start of file:"]
        assert agent._content_contains_marker("this has THINKING_CONTENT as a json key", markers)
        assert agent._content_contains_marker("(anchor) PS C:\\Users\\test> run", markers)
        assert agent._content_contains_marker("[PLANNER] Proposed plan: do things", markers)
        assert agent._content_contains_marker("--- START OF FILE: test.txt ---\nHello", markers)


@pytest.mark.asyncio
async def test_purge_contaminated_nodes_dry_run_returns_counts():
    # fake rows to return
    rows = [
        {"id": "abc123", "content": "combined_text snippet...", "metadata": "{'source':'file'}", "created_at": datetime.now(timezone.utc).isoformat(), "session_id": "sid-1", "category": "note"},
    ]
    fake_memory = FakeMemory(rows)
    agent = ArchivistAgent(memory=fake_memory, verifier=FakeVerifier(), settings=Settings())
    result = await agent.purge_contaminated_nodes(dry_run=True, markers=["combined_text"])
    assert isinstance(result, dict)
    assert result.get("found") >= 0
    assert result.get("deleted") == 0
