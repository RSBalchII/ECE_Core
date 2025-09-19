import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the components directory to the path so we can import the cache_manager
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'components'))

from context_cache.cache_manager import CacheManager, CacheEntry


class TestCacheManager(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        with patch('context_cache.cache_manager.redis.Redis') as mock_redis:
            # Mock the Redis client
            self.mock_redis_client = MagicMock()
            mock_redis.return_value = self.mock_redis_client
            
            # Mock the ping method to succeed
            self.mock_redis_client.ping.return_value = True
            
            # Create an instance of CacheManager
            self.cache_manager = CacheManager()
            
            # Configure the dbsize mock to return an integer
            self.mock_redis_client.dbsize.return_value = 0
    
    def test_init(self):
        """Test CacheManager initialization."""
        self.assertIsInstance(self.cache_manager, CacheManager)
        self.assertEqual(self.cache_manager.host, 'localhost')
        self.assertEqual(self.cache_manager.port, 6379)
    
    def test_store(self):
        """Test storing a value in the cache."""
        # Mock the set method to return True
        self.mock_redis_client.hset.return_value = True
        
        result = self.cache_manager.store('test_key', 'test_value')
        self.assertTrue(result)
        
        # Verify the hset method was called with correct arguments
        self.mock_redis_client.hset.assert_called_once()
    
    def test_store_with_embedding(self):
        """Test storing a value with embedding in the cache."""
        # Mock the set method to return True
        self.mock_redis_client.hset.return_value = True
        
        embedding = [0.1, 0.2, 0.3]
        result = self.cache_manager.store('test_key', 'test_value', embedding=embedding)
        self.assertTrue(result)
        
        # Verify the hset method was called
        self.mock_redis_client.hset.assert_called_once()
    
    def test_retrieve(self):
        """Test retrieving a value from the cache."""
        # Mock the hgetall method to return a value
        self.mock_redis_client.hgetall.return_value = {
            'value': 'test_value',
            'created_at': '2023-01-01T00:00:00',
            'access_count': '0'
        }
        self.mock_redis_client.incr.return_value = None
        
        result = self.cache_manager.retrieve('test_key')
        self.assertIsInstance(result, CacheEntry)
        self.assertEqual(result.key, 'test_key')
        self.assertEqual(result.value, 'test_value')
    
    def test_retrieve_not_found(self):
        """Test retrieving a non-existent value from the cache."""
        # Mock the hgetall method to return an empty dict
        self.mock_redis_client.hgetall.return_value = {}
        self.mock_redis_client.incr.return_value = None
        
        result = self.cache_manager.retrieve('non_existent_key')
        self.assertIsNone(result)
    
    def test_delete(self):
        """Test deleting a value from the cache."""
        # Mock the delete method to return 1 (indicating success)
        self.mock_redis_client.delete.return_value = 1
        
        result = self.cache_manager.delete('test_key')
        self.assertTrue(result)
        
        # Verify the delete method was called with correct arguments
        self.mock_redis_client.delete.assert_called_once_with('context_cache:test_key')
    
    def test_get_statistics(self):
        """Test getting cache statistics."""
        # Mock the get method to return specific values
        self.mock_redis_client.get.side_effect = lambda key: {
            'cache_stats:hits': '10',
            'cache_stats:misses': '5'
        }.get(key, '0')
        
        stats = self.cache_manager.get_statistics()
        self.assertEqual(stats['hits'], 10)
        self.assertEqual(stats['misses'], 5)
        self.assertEqual(stats['total_requests'], 15)
        self.assertAlmostEqual(stats['hit_rate'], 0.6667, places=4)
    
    def test_semantic_search(self):
        """Test semantic search functionality."""
        # This test would require a more complex mock of the Redis search functionality
        # For now, we'll just verify the method exists and can be called
        self.assertTrue(hasattr(self.cache_manager, 'semantic_search'))

    def test_trim_cache(self):
        """Test that the cache is trimmed to the max_size."""
        # Set a small max_size for testing
        self.cache_manager.max_size = 2
        
        # Mock the dbsize, keys, hget, and delete methods
        self.mock_redis_client.dbsize.return_value = 3
        self.mock_redis_client.keys.return_value = [
            b'context_cache:key2',
            b'context_cache:key1',
            b'context_cache:key3'
        ]
        self.mock_redis_client.hget.side_effect = lambda key, field: {
            b'context_cache:key1': {'created_at': '2023-01-01T00:00:00'},
            b'context_cache:key2': {'created_at': '2023-01-02T00:00:00'},
            b'context_cache:key3': {'created_at': '2023-01-03T00:00:00'},
        }.get(key, {}).get(field)
        self.mock_redis_client.delete.return_value = 1
        
        # Call the trim method directly for testing
        self.cache_manager._trim_cache()
        
        # Verify that the oldest key was deleted
        self.mock_redis_client.delete.assert_called_once_with(b'context_cache:key1')


if __name__ == '__main__':
    unittest.main()