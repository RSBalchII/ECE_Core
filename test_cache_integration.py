"""
Test script for the CacheManager integration with the main application
"""

import requests
import json
import time

# Wait a moment for the services to start
time.sleep(10)

# Test data
test_data = {
    "key": "test_key",
    "value": "test_value",
    "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
    "ttl": 3600
}

# Test storing data via direct API endpoint
print("Testing data storage via direct API endpoint...")
store_response = requests.post(
    "http://localhost:8001/cache/store",
    json=test_data
)

print("Store response:", store_response.json())

# Test retrieving data via direct API endpoint
print("\nTesting data retrieval via direct API endpoint...")
retrieve_response = requests.post(
    "http://localhost:8001/cache/retrieve",
    json={"key": "test_key"}
)

print("Retrieve response:", retrieve_response.json())

# Test semantic search via direct API endpoint
print("\nTesting semantic search via direct API endpoint...")
semantic_search_response = requests.post(
    "http://localhost:8001/cache/semantic_search",
    json={
        "query_embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
        "threshold": 0.8
    }
)

print("Semantic search response:", semantic_search_response.json())

# Test cache statistics via direct API endpoint
print("\nTesting cache statistics via direct API endpoint...")
stats_response = requests.get(
    "http://localhost:8001/cache/stats"
)

print("Stats response:", stats_response.json())

# Test chat endpoint with caching intent
print("\nTesting chat endpoint with caching intent...")
chat_data = {
    "message": "cache this information with key 'user_profile_123'",
    "context": {
        "cache_action": "store",
        "cache_key": "user_profile_123",
        "cache_value": "{\"name\": \"John Doe\", \"age\": 30}",
        "cache_embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
    }
}

chat_response = requests.post(
    "http://localhost:8001/chat",
    json=chat_data
)

print("Chat response:", chat_response.json())