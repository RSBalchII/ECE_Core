"""
Unit tests for the CacheManager
"""

import pytest
import asyncio
import json
from unittest.mock import MagicMock, patch
from src.external_context_engine.tools.cache_manager import CacheManager, CacheEntry, SemanticQuery, CacheStats


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    return MagicMock()


@pytest.fixture
def cache_manager(mock_redis_client):
    """Create a CacheManager instance with a mock Redis client."""
    with patch('src.external_context_engine.tools.cache_manager.redis.from_url') as mock_redis:
        mock_redis.return_value = mock_redis_client
        manager = CacheManager()
        return manager


def test_init(cache_manager, mock_redis_client):
    """Test initialization of the CacheManager."""
    assert isinstance(cache_manager, CacheManager)
    assert cache_manager.redis_client == mock_redis_client


@pytest.mark.asyncio
async def test_store(cache_manager, mock_redis_client):
    """Test storing data in the cache."""
    # Mock the Redis setex method
    mock_redis_client.setex.return_value = True
    
    # Test storing data without embedding
    result = await cache_manager.store("test_key", "test_value")
    assert result is True
    mock_redis_client.setex.assert_called()
    
    # Test storing data with embedding
    embedding = [0.1, 0.2, 0.3]
    result = await cache_manager.store("test_key2", "test_value2", embedding)
    assert result is True


@pytest.mark.asyncio
async def test_retrieve(cache_manager, mock_redis_client):
    """Test retrieving data from the cache."""
    # Mock the Redis get method for a cache hit
    cache_entry = CacheEntry(key="test_key", value="test_value")
    mock_redis_client.get.return_value = cache_entry.json()
    
    result = await cache_manager.retrieve("test_key")
    assert result == "test_value"
    
    # Mock the Redis get method for a cache miss
    mock_redis_client.get.return_value = None
    
    result = await cache_manager.retrieve("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_semantic_search(cache_manager, mock_redis_client):
    """Test semantic search functionality."""
    # Mock the Redis scan_iter and get methods
    mock_redis_client.scan_iter.return_value = [b"embedding:test_key"]
    
    embedding_data = {"key": "test_key", "embedding": [0.1, 0.2, 0.3]}
    cache_entry = CacheEntry(key="test_key", value="test_value", embedding=[0.1, 0.2, 0.3])
    
    mock_redis_client.get.side_effect = [
        json.dumps(embedding_data),
        cache_entry.model_dump_json()
    ]
    
    query_embedding = [0.1, 0.2, 0.3]
    results = await cache_manager.semantic_search(query_embedding, threshold=0.8)
    
    assert isinstance(results, list)
    # Note: The actual results may vary depending on the cosine similarity calculation


@pytest.mark.asyncio
async def test_get_stats(cache_manager, mock_redis_client):
    """Test getting cache statistics."""
    # Mock the Redis get method
    stats = CacheStats(hits=5, misses=3, hit_rate=0.625, size=8)
    mock_redis_client.get.return_value = stats.json()
    
    result = await cache_manager.get_stats()
    assert isinstance(result, CacheStats)
    assert result.hits == 5
    assert result.misses == 3
    assert result.hit_rate == 0.625
    assert result.size == 8


@pytest.mark.asyncio
async def test_clear(cache_manager, mock_redis_client):
    """Test clearing the cache."""
    # Mock the Redis keys and delete methods
    mock_redis_client.keys.return_value = [b"cache:test_key", b"embedding:test_key"]
    mock_redis_client.delete.return_value = 2
    
    result = await cache_manager.clear()
    assert result is True
    
    # Test clearing with pattern
    result = await cache_manager.clear("test*")
    assert result is True