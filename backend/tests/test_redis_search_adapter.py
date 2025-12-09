import pytest
import asyncio
import json
from src.vector_adapters.redis_vector_adapter import RedisVectorAdapter


@pytest.mark.asyncio
async def test_redis_adapter_create_index_and_ft_search_execute(monkeypatch):
    adapter = RedisVectorAdapter(redis_url="redis://localhost:6379")

    class FakeRedisExecuteClient:
        def __init__(self):
            self.store = {}
            self.index = set()
            self.execute_called = []

        async def ping(self):
            return True

        async def hset(self, key, mapping):
            self.store[key.replace("vec:", "")] = mapping

        async def sadd(self, key, value):
            self.index.add(value)

        async def smembers(self, key):
            return list(self.index)

        async def hgetall(self, key):
            return self.store.get(key.replace("vec:", "")) or {}

        async def srem(self, key, value):
            self.index.discard(value)

        async def delete(self, key):
            self.store.pop(key.replace("vec:", ""), None)

        async def execute_command(self, *args):
            # Save the command for verification
            self.execute_called.append(args)
            cmd = args[0]
            if cmd == "FT.CREATE":
                # pretend to succeed
                return True
            if cmd == "FT.SEARCH":
                # Return a mocked response in redis FT SEARCH format: [total, docId, {field: value}, ...]
                # We'll return one doc: vec:id1 with fields as bytes
                return [1, b"vec:id1", {b"node_id": b"node_a", b"chunk_index": b"0", b"metadata": b'{"source":"x"}'}]
            return None

    fake_client = FakeRedisExecuteClient()
    # Patch redis.from_url used in adapter.initialize to return our fake client
    import redis.asyncio as redis_asyncio
    async def fake_from_url(*args, **kwargs):
        return fake_client
    monkeypatch.setattr(redis_asyncio, "from_url", fake_from_url)
    # Force detection as if RediSearch is available
    adapter._redis_search_available = True
    adapter._index_created = False
    await adapter.initialize()

    # Index a chunk; should call execute_command FT.CREATE at first
    await adapter.index_chunk("id1", node_id="node_a", chunk_index=0, embedding=[0.2, 0.4], metadata={"k": "v"})
    assert adapter._vector_dim == 2
    assert adapter._index_created is True
    # Confirm FT.CREATE was called
    found = any(c[0] == "FT.CREATE" for c in fake_client.execute_called)
    assert found

    # Now query_vector -> will use FT.SEARCH via execute_command
    hits = await adapter.query_vector([0.2, 0.4], top_k=1)
    assert len(hits) == 1
    assert hits[0]["node_id"] == "node_a"
