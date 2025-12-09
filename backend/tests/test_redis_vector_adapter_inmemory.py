import pytest
from src.vector_adapters.redis_vector_adapter import RedisVectorAdapter


@pytest.mark.asyncio
async def test_redis_vector_adapter_inmemory_basic():
    adapter = RedisVectorAdapter(redis_url="redis://localhost:6379")
    # Force in-memory by not connecting
    adapter.client = None
    await adapter.index_chunk("e1", "n1", 0, [1.0, 0.0, 0.0], metadata={"text": "a"})
    await adapter.index_chunk("e2", "n2", 0, [0.0, 1.0, 0.0], metadata={"text": "b"})
    await adapter.index_chunk("e3", "n3", 0, [0.5, 0.5, 0.0], metadata={"text": "c"})
    res = await adapter.query_vector([1.0, 0.0, 0.0], top_k=3)
    assert len(res) == 3
    assert res[0]['embedding_id'] == 'e1'
    assert await adapter.get('e2') is not None
    await adapter.delete('e2')
    assert await adapter.get('e2') is None
