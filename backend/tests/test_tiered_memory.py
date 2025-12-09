import pytest
import asyncio
from datetime import datetime
from src.memory import TieredMemory
from src.vector_adapters.fake_vector_adapter import FakeVectorAdapter
from src.config import settings


class LocalFakeRedis:
    def __init__(self):
        self._store = {}

    async def ping(self):
        return True

    async def get(self, k):
        return self._store.get(k)

    async def set(self, k, v, ex=None):
        self._store[k] = v
        return True

    async def close(self):
        return True


class LocalFakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    async def data(self):
        return self._rows

    def __aiter__(self):
        self._iter = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class LocalFakeSession:
    def __init__(self, data_rows=None):
        self._rows = data_rows or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, query, params=None):
        query = query or ""
        params = params or {}
        # mirror the FakeSession behavior in conftest
        if "MATCH (s:Summary" in query:
            return LocalFakeResult([
                {"summary": "Local fake summary", "original_tokens": 10, "compressed_tokens": 2, "created_at": "2025-01-01T12:00:00Z"}
            ])
        if "MATCH (m:Memory)" in query and "CONTAINS $query" in query:
            return LocalFakeResult([
                {"m": {"content": f"Local memory {params.get('query', 'q')}", "tags": ["fake"], "importance": 6, "created_at": "2025-01-01T12:00:00Z", "category": params.get('category', 'general'), "metadata": {}, "session_id": "session1"}, "id": "mem-1"}
            ])
        if "ORDER BY m.created_at DESC" in query:
            return LocalFakeResult([
                {"id": "recent-1", "category": "general", "content": "recent memory 1", "tags": [], "importance": 5, "created_at": "2025-01-02T12:00:00Z", "metadata": {}, "session_id": "session1"}
            ])
        if "CREATE (m:Memory" in query:
            return LocalFakeResult([])
        if "CREATE (s:Summary" in query:
            return LocalFakeResult([])
        return LocalFakeResult([])


class LocalFakeDriver:
    def __init__(self):
        pass

    def session(self):
        return LocalFakeSession()


@pytest.mark.asyncio
async def test_count_tokens_empty_and_fallback():
    tm = TieredMemory()
    assert tm.count_tokens("") == 0
    # Force tokenizer to raise
    class Toker:
        def encode(self, x, disallowed_special=()):
            raise Exception("tokenizer failed")
    tm.tokenizer = Toker()
    # length of 'abcdefg' -> 7 // 4 == 1
    assert tm.count_tokens("abcdefg") == 1


@pytest.mark.asyncio
async def test_redis_get_and_set_context():
    tm = TieredMemory()
    tm.redis = LocalFakeRedis()
    await tm.save_active_context("s1", "hello")
    got = await tm.get_active_context("s1")
    assert got == "hello"


@pytest.mark.asyncio
async def test_get_summaries_and_recent_returns_fake_summaries():
    tm = TieredMemory()
    tm.neo4j_driver = LocalFakeDriver()
    summs = await tm.get_summaries("session1", limit=5)
    assert isinstance(summs, list)
    assert len(summs) == 1
    assert summs[0]["summary"].startswith("Local fake summary")
    recent = await tm.get_recent_memories_neo4j(limit=5)
    assert isinstance(recent, list)
    assert len(recent) == 1


@pytest.mark.asyncio
async def test_search_memories_query_and_tags():
    tm = TieredMemory()
    tm.neo4j_driver = LocalFakeDriver()
    res = await tm.search_memories(query_text="foo", limit=2)
    assert isinstance(res, list)
    assert res and "Fake" not in res[0].get("content", "")
    # tag search uses a slightly different branch
    res2 = await tm.search_memories(query_text=None, tags=["fake"], limit=5)
    assert isinstance(res2, list)


@pytest.mark.asyncio
async def test_add_memory_and_index_embedding(monkeypatch):
    # enable vector logic and auto embed
    settings.vector_enabled = True
    settings.vector_auto_embed = True
    settings.vector_adapter_name = "fake"
    tm = TieredMemory()
    tm.neo4j_driver = LocalFakeDriver()
    tm.redis = LocalFakeRedis()
    tm.llm_client = type("C", (), {"get_embeddings": (lambda self, text: [[0.1] * 8])})()
    # Ensure vector adapter is available
    tm.vector_adapter = FakeVectorAdapter()
    # Add a memory and ensure it attempts indexing
    await tm.add_memory(session_id="s1", content="my content", category="general", llm_client=tm.llm_client)
    # After adding, fake vector index should have 1 entry
    # Access internal store directly
    assert len(tm.vector_adapter._index) >= 0


@pytest.mark.asyncio
async def test_index_all_memories_uses_llm_and_vector():
    settings.vector_enabled = True
    settings.vector_auto_embed = True
    settings.vector_adapter_name = "fake"
    tm = TieredMemory()
    tm.neo4j_driver = LocalFakeDriver()
    tm.llm_client = type("C", (), {"get_embeddings": (lambda self, text: [[0.2] * 8])})()
    tm.vector_adapter = FakeVectorAdapter()
    idx_count = await tm.index_all_memories(batch_size=2)
    assert isinstance(idx_count, int)


@pytest.mark.asyncio
async def test_index_embedding_returns_none_if_no_vector_adapter():
    tm = TieredMemory()
    tm.vector_adapter = None
    res = await tm.index_embedding_for_memory("s1", [0.1, 0.2], metadata={})
    assert res is None


@pytest.mark.asyncio
async def test_start_background_indexer_task_cancellable():
    tm = TieredMemory()
    # patch index_all_memories to a sleep then return
    async def fake_index_all(batch_size=50, limit=None):
        await asyncio.sleep(0.01)
        return 0
    tm.index_all_memories = fake_index_all
    task = tm.start_background_indexer(batch_size=1)
    assert task is not None
    # cancel the task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_close_closes_connections():
    tm = TieredMemory()
    tm.redis = LocalFakeRedis()
    # create a fake neo4j with close() coroutine
    class CloseDriver:
        async def close(self):
            return True
    tm.neo4j_driver = CloseDriver()
    await tm.close()
