import pytest
import asyncio
import json
from src.memory import TieredMemory
from src.vector_adapters.redis_vector_adapter import RedisVectorAdapter
from src.config import settings



class FakeNeo4jResult:
    def __init__(self, records):
        self._records = records
    async def data(self):
        return self._records

class FakeSession:
    def __init__(self, records):
        self._records = records
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def run(self, query, params=None):
        return FakeNeo4jResult(self._records)

class FakeDriver:
    def __init__(self, records):
        self._records = records
    def session(self):
        return FakeSession(self._records)


@pytest.mark.asyncio
async def test_index_all_memories(monkeypatch):
    mem = TieredMemory()
    # Create fake records as Neo4j result
    records = [{"id": 1, "content": "alpha content", "session_id": "s1"}, {"id": 2, "content": "beta content", "session_id": "s2"}]
    mem.neo4j_driver = FakeDriver(records)
    # Use in-memory vector adapter
    mem.vector_adapter = RedisVectorAdapter(redis_url="redis://localhost:9999")
    await mem.vector_adapter.initialize()

    # Fake LLM client
    class FakeLLM:
        async def get_embeddings(self, text):
            return [[0.1, 0.9]]
    mem.llm_client = FakeLLM()

    count = await mem.index_all_memories(batch_size=2, limit=10)
    assert count >= 2
    # Confirm vector adapter contains at least one item
    hits = await mem.vector_adapter.query_vector([0.1, 0.9], top_k=10)
    assert len(hits) >= 1


def test_start_background_indexer(monkeypatch):
    mem = TieredMemory()
    # stub index_all_memories
    async def fake_index(batch_size=50, limit=None):
        return 0
    mem.index_all_memories = fake_index
    task = mem.start_background_indexer(batch_size=1, limit=1)
    assert hasattr(task, "cancel")
    import asyncio as _aio
    # give the event loop a moment to start the task, then cancel
    _aio.get_event_loop().run_until_complete(_aio.sleep(0.01))
    task.cancel()
    try:
        _aio.get_event_loop().run_until_complete(task)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_auto_embedding_default(monkeypatch):
    # Ensure settings for vector are enabled
    settings.vector_enabled = True
    settings.vector_auto_embed = True
    # Fake LLMClient to avoid network calls
    import src.llm as llm_mod
    class FakeLLM:
        async def get_embeddings(self, text):
            return [[0.3, 0.7]]

    monkeypatch.setattr(llm_mod, "LLMClient", lambda: FakeLLM())
    mem = TieredMemory()
    mem.vector_adapter = RedisVectorAdapter(redis_url="redis://localhost:9999")
    await mem.vector_adapter.initialize()
    # Neo4j driver to avoid write errors
    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def run(self, *args, **kwargs):
            return None
    class FakeDriver:
        def session(self):
            return FakeSession()
    mem.neo4j_driver = FakeDriver()
    await mem.initialize()
    # Ensure the mem.llm_client is correctly set to our fake one
    mem.llm_client = FakeLLM()
    # Now call add_memory and ensure embedding was auto computed and indexed
    await mem.add_memory(session_id="sauto", content="hello default", category="note")
    hits = await mem.vector_adapter.query_vector([0.3, 0.7], top_k=3)
    assert len(hits) >= 1


def test_memory_basic_sanity():
    """Test a few basic functions on a TieredMemory instance when services are unavailable."""
    mem = TieredMemory()
    # No redis/neo4j configured, these methods should handle gracefully
    assert mem.count_tokens("") == 0
    assert mem.count_tokens("hello there") > 0
    # Async functions that return defaults when connections are missing
    import asyncio
    loop = asyncio.get_event_loop()
    assert loop.run_until_complete(mem.get_active_context("none")) == ""
    assert loop.run_until_complete(mem.get_summaries("none")) == []
    assert loop.run_until_complete(mem.search_memories_fulltext("test")) == []
    assert loop.run_until_complete(mem.get_recent_memories_neo4j()) == []


@pytest.mark.asyncio
async def test_search_memories_tag_string_fallback(monkeypatch):
    mem = TieredMemory()
    # Fake a single record with tags stored as string
    records = [{"id": 1, "m": {"content": "x", "tags": "[\"test\"]", "importance": 5, "created_at": "2025-01-01T00:00:00Z", "metadata": "{}", "session_id": "s1", "category": "note"}}]
    class FakeQuerySession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def run(self, query, params=None):
            class R:
                async def __aiter__(self_inner):
                    for r in records:
                        yield r
            return R()
    class FakeDriver2:
        def session(self):
            return FakeQuerySession()
    mem.neo4j_driver = FakeDriver2()

    results = await mem.search_memories(tags=["test"], limit=5)
    assert len(results) >= 1
    assert "test" in results[0]["tags"]
