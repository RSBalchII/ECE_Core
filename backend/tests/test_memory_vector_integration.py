import pytest
from src.memory import TieredMemory
from src.vector_adapters.fake_vector_adapter import FakeVectorAdapter


@pytest.mark.asyncio
async def test_index_embedding_for_memory_with_fake_vector_adapter():
    tm = TieredMemory()
    # Force vector enabled and attach fake adapter for this memory
    tm._vector_enabled = True
    tm.vector_adapter = FakeVectorAdapter()
    await tm.vector_adapter.initialize()
    await tm.initialize()

    # Provide a fake llm_client with deterministic embedding
    class FakeLLM:
        async def get_embeddings(self, text):
            return [[1.0, 0.0, 0.0]]

    fake_llm = FakeLLM()
    # Add a memory and ensure indexing occurs
    await tm.add_memory(session_id='s1', content='Test content', category='test', tags=['t1'], importance=5, metadata=None, llm_client=fake_llm)
    # If vector adapter indexes, we should be able to find an embedding id by reading internal adapter storage
    if tm.vector_adapter and hasattr(tm.vector_adapter, '_index'):
        assert len(tm.vector_adapter._index) >= 1
        # The entry's node_id should be of format 's1:<timestamp>' because index_embedding_for_memory uses that
        keys = list(tm.vector_adapter._index.keys())
        assert any(k.startswith('s1:') for k in keys)
    else:
        pytest.skip('Vector adapter not configured for this environment')
