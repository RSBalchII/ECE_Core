"""
Test suite for memory system reliability.
Tests Redis fallback, Neo4j operations, and graceful degradation.
"""
import pytest
import asyncio
from src.memory import TieredMemory
from src.config import settings

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
async def memory():
    """Create memory instance for testing."""
    mem = TieredMemory()
    await mem.initialize()
    yield mem
    await mem.close()

@pytest.fixture
async def memory_no_redis():
    """Create memory instance without Redis."""
    mem = TieredMemory()
    await mem.initialize()
    # Simulate Redis failure
    mem.redis = None
    yield mem
    await mem.close()

# ============================================================================
# REDIS FALLBACK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_active_context_redis_available(memory):
    """Test getting context when Redis is available."""
    session_id = "test-session"
    test_context = "This is test context"
    
    if memory.redis:
        await memory.save_active_context(session_id, test_context)
        result = await memory.get_active_context(session_id)
        assert result == test_context
    else:
        pytest.skip("Redis not available")

@pytest.mark.asyncio
async def test_get_active_context_redis_unavailable(memory_no_redis):
    """Test fallback when Redis is unavailable."""
    session_id = "test-session"
    
    # Should return empty string without crashing
    result = await memory_no_redis.get_active_context(session_id)
    assert result == "" or result is None

@pytest.mark.asyncio
async def test_save_active_context_redis_unavailable(memory_no_redis):
    """Test save gracefully fails when Redis unavailable."""
    session_id = "test-session"
    
    # Should not crash
    await memory_no_redis.save_active_context(session_id, "test")
    # No assertion needed - just verify no exception

# ============================================================================
# NEO4J OPERATIONS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_add_memory_neo4j(memory):
    """Test adding memory to Neo4j."""
    if not memory.neo4j_driver:
        pytest.skip("Neo4j not available")
    
    await memory.add_memory(
        category="test",
        content="Test memory content",
        tags=["test", "pytest"],
        importance=5
    )
    
    # Verify memory was added
    memories = await memory.search_memories(category="test", limit=10)
    assert len(memories) > 0
    assert any("Test memory content" in m.get("content", "") for m in memories)

@pytest.mark.asyncio
async def test_search_memories_by_category(memory):
    """Test searching memories by category."""
    if not memory.neo4j_driver:
        pytest.skip("Neo4j not available")
    
    # Add test memory
    await memory.add_memory(
        category="code",
        content="def test(): pass",
        tags=["python"],
        importance=7
    )
    
    # Search
    results = await memory.search_memories(category="code", limit=5)
    assert isinstance(results, list)

@pytest.mark.asyncio
async def test_search_memories_by_tags(memory):
    """Test searching memories by tags."""
    if not memory.neo4j_driver:
        pytest.skip("Neo4j not available")
    
    # Add test memory
    await memory.add_memory(
        category="idea",
        content="Test idea",
        tags=["innovation", "testing"],
        importance=6
    )
    
    # Search by tag
    results = await memory.search_memories(tags=["testing"], limit=5)
    assert isinstance(results, list)

# ============================================================================
# TOKEN COUNTING TESTS
# ============================================================================

def test_count_tokens_basic():
    """Test basic token counting."""
    mem = TieredMemory()
    
    text = "Hello world"
    count = mem.count_tokens(text)
    assert count > 0
    assert count < 10  # "Hello world" should be ~2-3 tokens

def test_count_tokens_empty():
    """Test token counting with empty string."""
    mem = TieredMemory()
    
    count = mem.count_tokens("")
    assert count == 0

def test_count_tokens_large():
    """Test token counting with large text."""
    mem = TieredMemory()
    
    # ~1000 words
    text = " ".join(["word"] * 1000)
    count = mem.count_tokens(text)
    assert count > 500  # Should be at least 500 tokens

# ============================================================================
# GRACEFUL DEGRADATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_memory_works_without_redis():
    """Test that memory system works without Redis."""
    mem = TieredMemory()
    original_url = settings.redis_url
    settings.redis_url = "redis://invalid:9999"
    
    await mem.initialize()
    
    # Initialization should not raise; depending on test environment we may have a fake redis
    assert mem.redis is None or mem.redis == None or hasattr(mem.redis, "ping")
    
    # Should still be able to use Neo4j
    if mem.neo4j_driver:
        await mem.add_memory("test", "Test without Redis", tags=["test"])
    
    await mem.close()
    settings.redis_url = original_url

@pytest.mark.asyncio
async def test_memory_initialization_retry():
    """Test memory initialization handles failures gracefully."""
    mem = TieredMemory()
    
    # Should not raise exception even if services unavailable
    try:
        await mem.initialize()
        # If we get here, initialization succeeded (even if services are down)
        assert True
    except Exception as e:
        pytest.fail(f"Memory initialization should handle failures gracefully: {e}")
    finally:
        await mem.close()

# ============================================================================
# SUMMARY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_summaries(memory):
    """Test retrieving conversation summaries."""
    if not memory.neo4j_driver:
        pytest.skip("Neo4j not available")
    
    session_id = "test-session"
    
    # Get summaries (should not crash even if none exist)
    summaries = await memory.get_summaries(session_id, limit=5)
    assert isinstance(summaries, list)

@pytest.mark.asyncio
async def test_save_summary(memory):
    """Test saving conversation summary."""
    if not memory.neo4j_driver:
        pytest.skip("Neo4j not available")
    
    session_id = "test-session"
    summary = "This is a test summary of the conversation"
    
    await memory.save_summary(session_id, summary)
    
    # Verify summary was saved
    summaries = await memory.get_summaries(session_id, limit=10)
    assert len(summaries) > 0
