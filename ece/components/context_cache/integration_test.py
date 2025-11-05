#!/usr/bin/env python3
"""
Integration test for the CacheManager class.

This script tests the CacheManager with a real Redis instance.
"""

import sys
import os
import time

# Add the components directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "components"))

from context_cache.cache_manager import CacheManager, CacheEntry


def test_cache_manager():
    """Test the CacheManager with a real Redis instance."""
    print("Testing CacheManager with real Redis instance...")

    # Create a CacheManager instance
    cache_manager = CacheManager()

    # Test storing a simple value
    print("1. Testing store operation...")
    result = cache_manager.store("test_key", "test_value")
    print(f"   Store result: {result}")
    assert result == True, "Store operation failed"

    # Test retrieving a value
    print("2. Testing retrieve operation...")
    entry = cache_manager.retrieve("test_key")
    print(f"   Retrieved entry: {entry}")
    assert isinstance(entry, CacheEntry), "Retrieve operation failed"
    assert entry.key == "test_key", "Incorrect key"
    assert entry.value == "test_value", "Incorrect value"

    # Test storing a value with embedding
    print("3. Testing store with embedding...")
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    result = cache_manager.store(
        "embedding_key", "embedding_value", embedding=embedding
    )
    print(f"   Store with embedding result: {result}")
    assert result == True, "Store with embedding failed"

    # Test retrieving a value with embedding
    print("4. Testing retrieve with embedding...")
    entry = cache_manager.retrieve("embedding_key")
    print(f"   Retrieved entry with embedding: {entry}")
    assert isinstance(entry, CacheEntry), "Retrieve operation failed"
    assert entry.key == "embedding_key", "Incorrect key"
    assert entry.value == "embedding_value", "Incorrect value"
    assert entry.embedding == embedding, "Incorrect embedding"

    # Test deleting a value
    print("5. Testing delete operation...")
    result = cache_manager.delete("test_key")
    print(f"   Delete result: {result}")
    assert result == True, "Delete operation failed"

    # Verify the value was deleted
    entry = cache_manager.retrieve("test_key")
    assert entry is None, "Value was not deleted"

    # Test statistics
    print("6. Testing statistics...")
    stats = cache_manager.get_statistics()
    print(f"   Statistics: {stats}")
    assert "hits" in stats, "Missing hits in statistics"
    assert "misses" in stats, "Missing misses in statistics"

    # Test semantic search (basic functionality)
    print("7. Testing semantic search...")
    # Add a few more entries with embeddings for search
    cache_manager.store(
        "search_key1",
        "This is a test document about artificial intelligence",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
    )
    cache_manager.store(
        "search_key2",
        "This document discusses machine learning algorithms",
        embedding=[0.2, 0.3, 0.4, 0.5, 0.6],
    )
    cache_manager.store(
        "search_key3",
        "Natural language processing is a subfield of AI",
        embedding=[0.3, 0.4, 0.5, 0.6, 0.7],
    )

    # Perform a semantic search
    query_embedding = [0.15, 0.25, 0.35, 0.45, 0.55]
    results = cache_manager.semantic_search(query_embedding, top_k=2)
    print(f"   Semantic search results: {results}")
    # We expect some results, but the exact content depends on Redis
    # Just verify it's a list of CacheEntry objects
    assert isinstance(results, list), "Semantic search should return a list"
    if results:
        assert isinstance(results[0], CacheEntry), (
            "Semantic search should return CacheEntry objects"
        )

    print("All tests passed!")


if __name__ == "__main__":
    test_cache_manager()
