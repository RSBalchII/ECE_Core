import pytest
import asyncio
from src.vector_adapters.fake_vector_adapter import FakeVectorAdapter


@pytest.mark.asyncio
async def test_fake_vector_adapter_basic():
    a = FakeVectorAdapter()
    await a.initialize()
    await a.index_chunk(embedding_id="v1", node_id="n1", chunk_index=0, embedding=[1.0, 0.0, 0.0], metadata={"text": "a"})
    await a.index_chunk(embedding_id="v2", node_id="n2", chunk_index=0, embedding=[0.0, 1.0, 0.0], metadata={"text": "b"})
    await a.index_chunk(embedding_id="v3", node_id="n3", chunk_index=0, embedding=[0.5, 0.5, 0.0], metadata={"text": "c"})

    res = await a.query_vector([1.0, 0.0, 0.0], top_k=3)
    assert len(res) == 3
    assert res[0]['embedding_id'] == 'v1'
    assert res[1]['embedding_id'] in ('v3', 'v2')

    got = await a.get('v2')
    assert got['node_id'] == 'n2'

    await a.delete('v2')
    assert await a.get('v2') is None
