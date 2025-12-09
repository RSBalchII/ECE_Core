"""
C2C System Tests and Benchmarks

Validates cache pool functionality, semantic state compression, and cache fusion efficiency.
"""

import asyncio
import pytest
import time
from typing import List, Dict, Any
from retrieval.kv_cache_fusion import (
    KVCachePool, CacheManager, C2COptimizer, SemanticState, create_c2c_system
)


class TestKVCachePool:
    """Tests for KVCachePool functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_creation(self):
        """Test basic cache creation and retrieval."""
        pool = KVCachePool(ttl_seconds=600)
        
        cache_id = await pool.add_cache(
            session_id="test_session",
            source="system_prompt",
            content="This is a system prompt"
        )
        
        assert cache_id is not None
        assert isinstance(cache_id, str)
        assert "system_prompt" in cache_id
    
    @pytest.mark.asyncio
    async def test_cache_retrieval(self):
        """Test cache retrieval."""
        pool = KVCachePool(ttl_seconds=600)
        
        cache_id = await pool.add_cache(
            session_id="test_session",
            source="memory",
            content="Important memory content"
        )
        
        entry = await pool.get_cache("test_session", cache_id)
        
        assert entry is not None
        assert entry.cache_id == cache_id
        assert entry.source == "memory"
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss tracking."""
        pool = KVCachePool(ttl_seconds=600)
        
        # Try to get non-existent cache
        entry = await pool.get_cache("test_session", "nonexistent_id")
        
        assert entry is None
        assert pool.metrics["test_session"].miss_count == 1
        assert pool.metrics["test_session"].hit_count == 0
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cache TTL expiration."""
        pool = KVCachePool(ttl_seconds=1)  # 1 second TTL
        
        cache_id = await pool.add_cache(
            session_id="test_session",
            source="memory",
            content="Will expire soon"
        )
        
        # Should be retrievable immediately
        entry = await pool.get_cache("test_session", cache_id)
        assert entry is not None
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired now
        entry = await pool.get_cache("test_session", cache_id)
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_cache_by_source(self):
        """Test retrieving caches by source type."""
        pool = KVCachePool(ttl_seconds=600)
        
        # Add multiple caches
        await pool.add_cache("session1", "system_prompt", "System prompt")
        await pool.add_cache("session1", "memory", "Memory 1")
        await pool.add_cache("session1", "memory", "Memory 2")
        await pool.add_cache("session1", "reasoning", "Reasoning 1")
        
        # Retrieve by source
        memories = await pool.get_cached_by_source("session1", "memory")
        assert len(memories) == 2
        
        reasoning = await pool.get_cached_by_source("session1", "reasoning")
        assert len(reasoning) == 1
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test explicit cache invalidation."""
        pool = KVCachePool(ttl_seconds=600)
        
        cache_id = await pool.add_cache(
            session_id="test_session",
            source="memory",
            content="This will be invalidated"
        )
        
        # Verify it exists
        entry = await pool.get_cache("test_session", cache_id)
        assert entry is not None
        
        # Invalidate
        result = await pool.invalidate_cache("test_session", cache_id)
        assert result is True
        
        # Should no longer exist
        entry = await pool.get_cache("test_session", cache_id)
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_source_invalidation(self):
        """Test invalidating all caches of a source."""
        pool = KVCachePool(ttl_seconds=600)
        
        # Add memories and reasoning caches
        mem_ids = []
        for i in range(3):
            cache_id = await pool.add_cache(
                session_id="session1",
                source="memory",
                content=f"Memory {i}"
            )
            mem_ids.append(cache_id)
        
        await pool.add_cache("session1", "reasoning", "Some reasoning")
        
        # Invalidate all memories
        await pool.invalidate_source("session1", "memory")
        
        # Memories should be gone
        for cache_id in mem_ids:
            entry = await pool.get_cache("session1", cache_id)
            assert entry is None
        
        # But reasoning should remain
        reasoning = await pool.get_cached_by_source("session1", "reasoning")
        assert len(reasoning) == 1
    
    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self):
        """Test cache metrics and hit rate."""
        pool = KVCachePool(ttl_seconds=600)
        
        cache_id = await pool.add_cache(
            session_id="session1",
            source="memory",
            content="Content"
        )
        
        # Generate some hits and misses
        await pool.get_cache("session1", cache_id)  # Hit
        await pool.get_cache("session1", cache_id)  # Hit
        await pool.get_cache("session1", "fake")    # Miss
        await pool.get_cache("session1", "fake2")   # Miss
        
        metrics = pool.metrics["session1"]
        assert metrics.hit_count == 2
        assert metrics.miss_count == 2
        assert metrics.hit_rate() == 0.5


class TestCacheManager:
    """Tests for CacheManager functionality."""
    
    @pytest.mark.asyncio
    async def test_system_prompt_caching(self):
        """Test system prompt caching strategy."""
        pool = KVCachePool(ttl_seconds=600)
        manager = CacheManager(pool)
        
        prompt = "You are a helpful assistant."
        cache_id = await manager.cache_system_prompt("session1", prompt)
        
        assert cache_id is not None
        entry = await pool.get_cache("session1", cache_id)
        assert entry is not None
        assert entry.source == "system_prompt"
    
    @pytest.mark.asyncio
    async def test_semantic_state_caching(self):
        """Test semantic state compression and caching."""
        pool = KVCachePool(ttl_seconds=600)
        manager = CacheManager(pool)
        
        state = SemanticState(
            iteration=1,
            state_id="test_state_1",
            reasoning_text="We determined that X is related to Y.",
            key_entities=["X", "Y", "Z"],
            decisions=["Chose option A"],
            open_questions=["What about B?"],
            compressed_tokens=50
        )
        
        await manager.cache_semantic_state("session1", state)
        
        retrieved = await manager.get_semantic_state("session1", 1)
        assert retrieved is not None
        assert retrieved.iteration == 1
        assert retrieved.key_entities == ["X", "Y", "Z"]
    
    @pytest.mark.asyncio
    async def test_memory_caching(self):
        """Test caching retrieved memories."""
        pool = KVCachePool(ttl_seconds=600)
        manager = CacheManager(pool)
        
        memories = [
            {"content": "Memory about topic A"},
            {"content": "Memory about topic B"},
            {"content": "Memory about topic C"}
        ]
        
        cache_ids = await manager.cache_retrieved_memories("session1", memories)
        
        assert len(cache_ids) == 3
        for cache_id in cache_ids:
            entry = await pool.get_cache("session1", cache_id)
            assert entry is not None
            assert entry.source == "memory"
    
    @pytest.mark.asyncio
    async def test_fusion_efficiency_estimation(self):
        """Test cache fusion efficiency estimation."""
        pool = KVCachePool(ttl_seconds=600)
        manager = CacheManager(pool)
        
        # Add some cached content
        await pool.add_cache("session1", "system_prompt", "System prompt here" * 50)
        await pool.add_cache("session1", "memory", "Memory content" * 50)
        await pool.add_cache("session1", "memory", "Another memory" * 50)
        
        # Estimate fusion efficiency for new content
        efficiency = await manager.estimate_fusion_efficiency(
            "session1",
            "New query content here"
        )
        
        assert "efficiency_ratio" in efficiency
        assert "estimated_speedup" in efficiency
        assert efficiency["cached_entries"] >= 2
    
    @pytest.mark.asyncio
    async def test_cache_merging(self):
        """Test cache merging operation."""
        pool = KVCachePool(ttl_seconds=600)
        manager = CacheManager(pool)
        
        # Create multiple cache entries
        cache_ids = []
        for i in range(3):
            cache_id = await pool.add_cache(
                session_id="session1",
                source="memory",
                content=f"Memory content {i}" * 20
            )
            cache_ids.append(cache_id)
        
        # Merge them
        result = await manager.merge_caches("session1", cache_ids)
        
        assert result["merged"] is True
        assert result["entries_merged"] == 3
        assert "merged_cache_id" in result


class TestSemanticState:
    """Tests for SemanticState functionality."""
    
    def test_semantic_state_creation(self):
        """Test semantic state creation."""
        state = SemanticState(
            iteration=0,
            state_id="state_1",
            reasoning_text="Initial reasoning",
            key_entities=["Entity1", "Entity2"],
            decisions=[],
            open_questions=["Question 1?"],
            compressed_tokens=100
        )
        
        assert state.iteration == 0
        assert len(state.key_entities) == 2
        assert state.compressed_tokens == 100
    
    def test_semantic_state_serialization(self):
        """Test semantic state serialization/deserialization."""
        state = SemanticState(
            iteration=2,
            state_id="state_2",
            reasoning_text="We found that...",
            key_entities=["A", "B"],
            decisions=["Decision 1"],
            open_questions=["Q1?", "Q2?"],
            compressed_tokens=150,
            kv_cache_id="cache_123"
        )
        
        # Serialize
        data = state.to_dict()
        
        # Deserialize
        recovered = SemanticState.from_dict(data)
        
        assert recovered.iteration == state.iteration
        assert recovered.key_entities == state.key_entities
        assert recovered.kv_cache_id == state.kv_cache_id
    
    def test_semantic_state_timestamp(self):
        """Test automatic timestamp assignment."""
        state = SemanticState(
            iteration=0,
            state_id="test",
            reasoning_text="Test",
            key_entities=[],
            decisions=[],
            open_questions=[],
            compressed_tokens=50
        )
        
        assert state.timestamp is not None
        assert isinstance(state.timestamp, float)


class TestC2COptimizer:
    """Tests for C2COptimizer."""
    
    @pytest.mark.asyncio
    async def test_optimization_logging(self):
        """Test logging of LLM calls for optimization."""
        pool = KVCachePool(ttl_seconds=600)
        manager = CacheManager(pool)
        optimizer = C2COptimizer(manager)
        
        # Log some calls
        await optimizer.log_call("session1", "query", 500, 100)
        await optimizer.log_call("session1", "reasoning", 800, 150)
        await optimizer.log_call("session1", "reasoning", 800, 150)
        
        assert len(optimizer.call_history["session1"]) == 3
    
    @pytest.mark.asyncio
    async def test_should_use_cache(self):
        """Test cache usage decision logic."""
        pool = KVCachePool(ttl_seconds=600)
        manager = CacheManager(pool)
        optimizer = C2COptimizer(manager)
        
        # System prompts should always be cached
        assert await optimizer.should_use_cache("session1", "system_prompt") is True
        
        # Single call - minimal benefit
        await optimizer.log_call("session1", "query", 500, 100)
        assert await optimizer.should_use_cache("session2", "retrieval") is False
        
        # Multiple calls - caching beneficial
        await optimizer.log_call("session2", "query", 1000, 200)
        await optimizer.log_call("session2", "reasoning", 1200, 200)
        assert await optimizer.should_use_cache("session2", "retrieval") is True
    
    @pytest.mark.asyncio
    async def test_optimization_recommendation(self):
        """Test optimization strategy recommendations."""
        pool = KVCachePool(ttl_seconds=600)
        manager = CacheManager(pool)
        optimizer = C2COptimizer(manager)
        
        # No history - no recommendation
        rec = await optimizer.get_optimization_recommendation("session1")
        assert rec["recommendation"] == "none"
        
        # Add iterative call history
        for i in range(3):
            await optimizer.log_call("session2", "reasoning", 1500, 200)
        
        rec = await optimizer.get_optimization_recommendation("session2")
        assert "iterative_state_compression" in rec.get("recommended_strategies", [])
        assert rec["total_calls"] == 3


class TestIntegration:
    """Integration tests for complete C2C system."""
    
    @pytest.mark.asyncio
    async def test_complete_c2c_workflow(self):
        """Test complete C2C workflow."""
        pool, manager, optimizer = await create_c2c_system()
        
        session_id = "integration_test"
        
        # Setup
        system_prompt_id = await manager.cache_system_prompt(
            session_id,
            "You are a helpful assistant."
        )
        assert system_prompt_id is not None
        
        # Add memories
        memories = [
            {"content": f"Memory {i}" * 20} for i in range(3)
        ]
        memory_ids = await manager.cache_retrieved_memories(session_id, memories)
        assert len(memory_ids) == 3
        
        # Add semantic state
        state = SemanticState(
            iteration=0,
            state_id="workflow_state_0",
            reasoning_text="Starting reasoning process",
            key_entities=["Key1", "Key2"],
            decisions=["Decision1"],
            open_questions=["Q1?"],
            compressed_tokens=100
        )
        await manager.cache_semantic_state(session_id, state)
        
        # Verify retrieval
        retrieved_state = await manager.get_semantic_state(session_id, 0)
        assert retrieved_state is not None
        assert retrieved_state.key_entities == ["Key1", "Key2"]
        
        # Check metrics
        stats = await manager.get_fusion_stats(session_id)
        assert stats["cached_memories"] == 3
        assert stats["active_states"] == 1
        
        # Cleanup
        await pool.cleanup_session(session_id)


# Benchmark tests
class TestBenchmarks:
    """Performance benchmarks for C2C operations."""
    
    @pytest.mark.asyncio
    async def test_cache_speed(self):
        """Benchmark cache operations."""
        pool = KVCachePool(ttl_seconds=600)
        
        # Benchmark cache creation
        start = time.time()
        for i in range(100):
            await pool.add_cache(
                session_id="benchmark",
                source="memory",
                content=f"Memory content {i}" * 10
            )
        creation_time = time.time() - start
        
        print(f"\nCache creation (100 entries): {creation_time:.3f}s ({100/creation_time:.0f} ops/sec)")
        assert creation_time < 1.0  # Should complete in under 1 second
    
    @pytest.mark.asyncio
    async def test_cache_retrieval_speed(self):
        """Benchmark cache retrieval."""
        pool = KVCachePool(ttl_seconds=600)
        
        # Pre-populate
        cache_ids = []
        for i in range(50):
            cache_id = await pool.add_cache(
                session_id="benchmark",
                source="memory",
                content=f"Memory {i}" * 10
            )
            cache_ids.append(cache_id)
        
        # Benchmark retrieval
        start = time.time()
        for _ in range(3):  # Multiple passes
            for cache_id in cache_ids:
                await pool.get_cache("benchmark", cache_id)
        retrieval_time = time.time() - start
        
        total_retrievals = len(cache_ids) * 3
        print(f"\nCache retrievals ({total_retrievals}): {retrieval_time:.3f}s ({total_retrievals/retrieval_time:.0f} ops/sec)")
        assert retrieval_time < 1.0
    
    @pytest.mark.asyncio
    async def test_fusion_speed(self):
        """Benchmark cache fusion."""
        pool, manager, optimizer = await create_c2c_system()
        
        # Setup session with multiple caches
        session_id = "fusion_benchmark"
        cache_ids = []
        for i in range(10):
            cache_id = await pool.add_cache(
                session_id=session_id,
                source="memory",
                content=f"Content {i}" * 50
            )
            cache_ids.append(cache_id)
        
        # Benchmark fusion
        start = time.time()
        result = await manager.merge_caches(session_id, cache_ids)
        fusion_time = time.time() - start
        
        print(f"\nCache fusion (10 entries): {fusion_time:.6f}s")
        assert result["merged"] is True
        assert fusion_time < 0.1


# Run with: pytest retrieval/test_c2c_fusion.py -v
if __name__ == "__main__":
    # Quick sanity check without pytest
    async def quick_test():
        print("Running C2C quick sanity check...")
        
        # Create system
        pool, manager, optimizer = await create_c2c_system()
        
        # Test basic flow
        session = "test"
        
        # Cache system prompt
        sys_id = await manager.cache_system_prompt(session, "System prompt")
        print(f"✓ System prompt cached: {sys_id}")
        
        # Cache memories
        mems = await manager.cache_retrieved_memories(
            session,
            [{"content": "Memory 1"}, {"content": "Memory 2"}]
        )
        print(f"✓ Memories cached: {len(mems)} items")
        
        # Cache semantic state
        state = SemanticState(
            iteration=0,
            state_id="test",
            reasoning_text="Test reasoning",
            key_entities=["E1"],
            decisions=[],
            open_questions=[],
            compressed_tokens=50
        )
        await manager.cache_semantic_state(session, state)
        print(f"✓ Semantic state cached")
        
        # Get stats
        stats = await manager.get_fusion_stats(session)
        print(f"✓ Cache stats retrieved: {stats['cached_memories']} memories")
        
        await pool.cleanup_session(session)
        print("\n✓ All quick tests passed!")
    
    asyncio.run(quick_test())
