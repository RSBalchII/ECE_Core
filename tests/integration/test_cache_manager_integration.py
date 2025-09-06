"""
Integration tests for the CacheManager with a real Redis instance
"""

import pytest
import asyncio
from src.external_context_engine.tools.cache_manager import CacheManager, CacheEntry, SemanticQuery, CacheStats


class TestCacheManagerIntegration:
    """Integration tests for the CacheManager with a real Redis instance."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Initialize the CacheManager with test Redis credentials
        self.cache_manager = CacheManager(
            config={
                "redis_url": "redis://localhost:6379",
                "default_ttl": 60,  # 1 minute for testing
                "max_size": 1000
            }
        )
        
        # Clear the cache before each test
        asyncio.run(self.cache_manager.clear())
    
    def teardown_method(self):
        """Tear down test fixtures after each test method."""
        # Clear the cache after each test
        asyncio.run(self.cache_manager.clear())
        
        # Close the Redis connection
        self.cache_manager.close()
    
    def test_store_and_retrieve(self):
        """Test storing and retrieving data from the cache."""
        # Store data in the cache
        key = "test_key"
        value = "test_value"
        result = asyncio.run(self.cache_manager.store(key, value))
        assert result is True
        
        # Retrieve the data
        retrieved_value = asyncio.run(self.cache_manager.retrieve(key))
        assert retrieved_value == value
        
        # Try to retrieve non-existent data
        nonexistent_value = asyncio.run(self.cache_manager.retrieve("nonexistent_key"))
        assert nonexistent_value is None
    
    def test_store_with_embedding_and_semantic_search(self):
        """Test storing data with embedding and performing semantic search."""
        # Store data with embedding
        key = "test_key"
        value = "test_value"
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = asyncio.run(self.cache_manager.store(key, value, embedding))
        assert result is True
        
        # Perform semantic search with identical embedding
        similar_entries = asyncio.run(self.cache_manager.semantic_search(embedding, threshold=0.9))
        assert len(similar_entries) >= 1
        
        # Check that the retrieved entry matches
        found_entry = False
        for entry in similar_entries:
            if entry.key == key and entry.value == value:
                found_entry = True
                break
        assert found_entry
    
    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        # Get initial stats
        initial_stats = asyncio.run(self.cache_manager.get_stats())
        assert isinstance(initial_stats, CacheStats)
        
        # Store and retrieve data to update stats
        key = "test_key"
        value = "test_value"
        asyncio.run(self.cache_manager.store(key, value))
        
        # Cache miss
        asyncio.run(self.cache_manager.retrieve("nonexistent_key"))
        
        # Cache hit
        asyncio.run(self.cache_manager.retrieve(key))
        
        # Get updated stats
        updated_stats = asyncio.run(self.cache_manager.get_stats())
        assert updated_stats.hits >= 1
        assert updated_stats.misses >= 1
        assert updated_stats.size >= 1
    
    def test_cache_clear(self):
        """Test clearing the cache."""
        # Store some data
        asyncio.run(self.cache_manager.store("key1", "value1"))
        asyncio.run(self.cache_manager.store("key2", "value2"))
        
        # Verify data is stored
        value1 = asyncio.run(self.cache_manager.retrieve("key1"))
        value2 = asyncio.run(self.cache_manager.retrieve("key2"))
        assert value1 == "value1"
        assert value2 == "value2"
        
        # Clear the cache
        result = asyncio.run(self.cache_manager.clear())
        assert result is True
        
        # Verify data is cleared
        cleared_value1 = asyncio.run(self.cache_manager.retrieve("key1"))
        cleared_value2 = asyncio.run(self.cache_manager.retrieve("key2"))
        assert cleared_value1 is None
        assert cleared_value2 is None
        
        # Verify stats are reset
        stats = asyncio.run(self.cache_manager.get_stats())
        assert stats.size == 0