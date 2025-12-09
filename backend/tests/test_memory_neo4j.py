import pytest
from unittest.mock import MagicMock, AsyncMock
from src.memory import TieredMemory

@pytest.mark.asyncio
async def test_memory_initialization():
    """Test that memory initializes correctly with fakes."""
    mem = TieredMemory()
    await mem.initialize()
    assert mem.redis is not None
    assert mem.neo4j_driver is not None

@pytest.mark.asyncio
async def test_add_memory():
    """Test adding a memory."""
    mem = TieredMemory()
    await mem.initialize()
    
    # Should not raise exception
    await mem.add_memory(
        session_id="test-session",
        content="Test memory content",
        category="test",
        importance=5
    )

@pytest.mark.asyncio
async def test_search_memories_query():
    """Test searching memories with a query string."""
    mem = TieredMemory()
    await mem.initialize()
    
    results = await mem.search_memories(query_text="fake")
    assert len(results) > 0
    assert "memory matching" in results[0]["content"].lower()
    assert results[0]["importance"] == 8

@pytest.mark.asyncio
async def test_get_recent_memories():
    """Test retrieving recent memories."""
    mem = TieredMemory()
    await mem.initialize()
    
    results = await mem.get_recent_memories_neo4j(limit=5)
    assert len(results) == 2
    assert results[0]["id"] == "fake-mem-recent-1"
    assert results[1]["id"] == "fake-mem-recent-2"

@pytest.mark.asyncio
async def test_get_summaries():
    """Test retrieving summaries."""
    mem = TieredMemory()
    await mem.initialize()
    
    summaries = await mem.get_summaries("test-session")
    assert len(summaries) == 1
    assert summaries[0]["summary"] == "Fake summary of previous conversation"

@pytest.mark.asyncio
async def test_index_all_memories_auto_embed():
    """Test batch indexing with auto-embedding."""
    # Mock LLM client for embeddings
    mock_llm = MagicMock()
    mock_llm.get_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    
    mem = TieredMemory(llm_client=mock_llm)
    # Force vector adapter to be present (it might be None if settings disable it)
    mem.vector_adapter = AsyncMock()
    mem.vector_adapter.index_chunk = AsyncMock()
    
    await mem.initialize()
    
    # Should process the 2 recent memories from our fake driver
    count = await mem.index_all_memories(batch_size=10)
    
    assert count == 2
    assert mock_llm.get_embeddings.call_count == 2
    assert mem.vector_adapter.index_chunk.call_count == 2
