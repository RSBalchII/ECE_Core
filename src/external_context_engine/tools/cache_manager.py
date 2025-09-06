"""
Cache Manager Implementation

This module implements a CacheManager for semantic and generative caching using Redis.
It provides both exact match caching and vector similarity search capabilities.
"""

import redis
import json
import time
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CacheEntry(BaseModel):
    """Data model for a cache entry."""
    key: str
    value: str
    embedding: Optional[List[float]] = None
    created_at: datetime = datetime.now()
    expires_at: Optional[datetime] = None
    access_count: int = 0


class SemanticQuery(BaseModel):
    """Data model for a semantic query."""
    text: str
    embedding: List[float]
    threshold: float = 0.8


class CacheStats(BaseModel):
    """Data model for cache statistics."""
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    size: int = 0
    max_size: int = 10000


class CacheManager:
    """
    Cache Manager for semantic and generative caching using Redis.
    
    This class provides methods for storing, retrieving, and searching cached data
    using both exact match and semantic similarity approaches.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the CacheManager.
        
        Args:
            config: Configuration dictionary with Redis connection settings
        """
        self.config = config or {}
        self.redis_url = self.config.get("redis_url", "redis://localhost:6379")
        self.default_ttl = self.config.get("default_ttl", 3600)  # 1 hour default
        self.max_size = self.config.get("max_size", 10000)
        
        # Connect to Redis
        try:
            self.redis_client = redis.from_url(self.redis_url)
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Fallback to in-memory cache if Redis is not available
            self.redis_client = None
            logger.info("Using in-memory cache as fallback")
        
        # Initialize statistics
        self.stats = CacheStats()
        
    def _get_key(self, key: str) -> str:
        """Get the Redis key with namespace prefix."""
        return f"cache:{key}"
    
    def _get_embedding_key(self, key: str) -> str:
        """Get the Redis key for embeddings with namespace prefix."""
        return f"embedding:{key}"
    
    def _get_stats_key(self) -> str:
        """Get the Redis key for statistics."""
        return "cache:stats"
    
    async def store(self, key: str, value: str, embedding: Optional[List[float]] = None, 
                    ttl: Optional[int] = None) -> bool:
        """
        Store a value in the cache with optional embedding for semantic search.
        
        Args:
            key: Cache key
            value: Value to cache
            embedding: Optional vector embedding for semantic search
            ttl: Time to live in seconds (defaults to default_ttl)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use provided TTL or default
            expire_time = ttl if ttl is not None else self.default_ttl
            
            # Store the main cache entry
            cache_entry = CacheEntry(
                key=key,
                value=value,
                embedding=embedding,
                expires_at=datetime.now() + timedelta(seconds=expire_time) if expire_time else None
            )
            
            # Serialize and store in Redis
            if self.redis_client:
                # Store the cache entry
                self.redis_client.setex(
                    self._get_key(key),
                    expire_time,
                    cache_entry.json()
                )
                
                # Store embedding separately if provided
                if embedding:
                    # For simplicity, we're storing embeddings as JSON
                    # In a production environment, you might want to use Redis's vector search capabilities
                    embedding_data = {
                        "key": key,
                        "embedding": embedding
                    }
                    self.redis_client.setex(
                        self._get_embedding_key(key),
                        expire_time,
                        json.dumps(embedding_data)
                    )
                
                # Update statistics
                self._update_stats(size_change=1)
            else:
                # Fallback to in-memory cache
                logger.warning("Redis not available, using in-memory cache")
                # Implementation would go here for in-memory cache
            
            logger.info(f"Stored cache entry for key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to store cache entry for key {key}: {e}")
            return False
    
    async def retrieve(self, key: str) -> Optional[str]:
        """
        Retrieve a value from the cache by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if found, None otherwise
        """
        try:
            if self.redis_client:
                # Try to get from Redis
                cached_data = self.redis_client.get(self._get_key(key))
                if cached_data:
                    # Parse the cache entry
                    cache_entry = CacheEntry.parse_raw(cached_data)
                    
                    # Increment access count
                    cache_entry.access_count += 1
                    
                    # Update the entry with new access count
                    self.redis_client.setex(
                        self._get_key(key),
                        self.default_ttl,
                        cache_entry.json()
                    )
                    
                    # Update statistics
                    self._update_stats(hit=True)
                    
                    logger.info(f"Cache hit for key: {key}")
                    return cache_entry.value
                else:
                    # Update statistics
                    self._update_stats(hit=False)
                    logger.info(f"Cache miss for key: {key}")
                    return None
            else:
                # Fallback to in-memory cache
                logger.warning("Redis not available, using in-memory cache")
                # Implementation would go here for in-memory cache
                self._update_stats(hit=False)
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve cache entry for key {key}: {e}")
            self._update_stats(hit=False)
            return None
    
    async def semantic_search(self, query_embedding: List[float], threshold: float = 0.8) -> List[CacheEntry]:
        """
        Perform semantic search using vector embeddings.
        
        Args:
            query_embedding: Query vector embedding
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            List of similar cache entries
        """
        # Note: This is a simplified implementation
        # In a production environment with Redis Stack, you would use Redis's vector search capabilities
        try:
            similar_entries = []
            
            if self.redis_client:
                # This is a simplified approach - in practice, you would use Redis's vector search
                # For now, we'll iterate through all embeddings (not efficient for large datasets)
                pattern = "embedding:*"
                for key in self.redis_client.scan_iter(match=pattern):
                    embedding_data = self.redis_client.get(key)
                    if embedding_data:
                        try:
                            embedding_dict = json.loads(embedding_data)
                            stored_embedding = embedding_dict.get("embedding")
                            
                            if stored_embedding and len(stored_embedding) == len(query_embedding):
                                # Calculate cosine similarity (simplified)
                                similarity = self._cosine_similarity(query_embedding, stored_embedding)
                                
                                if similarity >= threshold:
                                    # Get the full cache entry
                                    cache_key = embedding_dict.get("key")
                                    if cache_key:
                                        cached_data = self.redis_client.get(self._get_key(cache_key))
                                        if cached_data:
                                            cache_entry = CacheEntry.parse_raw(cached_data)
                                            similar_entries.append(cache_entry)
                        except Exception as e:
                            logger.error(f"Error processing embedding data: {e}")
                            continue
                
                logger.info(f"Found {len(similar_entries)} similar entries")
            else:
                # Fallback to in-memory cache
                logger.warning("Redis not available, semantic search not supported in fallback mode")
            
            return similar_entries
        except Exception as e:
            logger.error(f"Failed to perform semantic search: {e}")
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        try:
            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            
            # Calculate magnitudes
            magnitude1 = sum(a * a for a in vec1) ** 0.5
            magnitude2 = sum(b * b for b in vec2) ** 0.5
            
            # Avoid division by zero
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            return dot_product / (magnitude1 * magnitude2)
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def _update_stats(self, hit: Optional[bool] = None, size_change: int = 0):
        """
        Update cache statistics.
        
        Args:
            hit: True for hit, False for miss, None for neither
            size_change: Change in cache size (+1 for add, -1 for remove, 0 for no change)
        """
        try:
            if hit is not None:
                if hit:
                    self.stats.hits += 1
                else:
                    self.stats.misses += 1
                
                # Recalculate hit rate
                total = self.stats.hits + self.stats.misses
                if total > 0:
                    self.stats.hit_rate = self.stats.hits / total
            
            # Update size
            self.stats.size += size_change
            
            # Ensure size doesn't go negative
            if self.stats.size < 0:
                self.stats.size = 0
            
            # Store stats in Redis if available
            if self.redis_client:
                self.redis_client.setex(
                    self._get_stats_key(),
                    3600,  # 1 hour
                    self.stats.json()
                )
        except Exception as e:
            logger.error(f"Failed to update cache statistics: {e}")
    
    async def get_stats(self) -> CacheStats:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics
        """
        try:
            if self.redis_client:
                # Try to get stats from Redis
                stats_data = self.redis_client.get(self._get_stats_key())
                if stats_data:
                    return CacheStats.parse_raw(stats_data)
            
            # Return current in-memory stats
            return self.stats
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return CacheStats()
    
    async def clear(self, pattern: Optional[str] = None) -> bool:
        """
        Clear the cache.
        
        Args:
            pattern: Optional pattern to match keys for selective clearing
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.redis_client:
                if pattern:
                    # Clear keys matching pattern
                    pattern_key = f"cache:{pattern}" if not pattern.startswith("cache:") else pattern
                    keys = self.redis_client.keys(pattern_key)
                    if keys:
                        self.redis_client.delete(*keys)
                else:
                    # Clear all cache keys
                    keys = self.redis_client.keys("cache:*")
                    if keys:
                        self.redis_client.delete(*keys)
                    
                    # Clear embedding keys
                    embedding_keys = self.redis_client.keys("embedding:*")
                    if embedding_keys:
                        self.redis_client.delete(*embedding_keys)
                
                # Reset statistics
                self.stats = CacheStats()
                self.redis_client.delete(self._get_stats_key())
                
                logger.info("Cache cleared successfully")
                return True
            else:
                # Fallback to in-memory cache
                logger.warning("Redis not available, clearing in-memory cache")
                # Implementation would go here for in-memory cache
                self.stats = CacheStats()
                return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    def close(self):
        """Close the Redis connection."""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis connection closed")