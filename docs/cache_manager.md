# Cache Manager Documentation

## Overview

The CacheManager is responsible for managing the short-term memory layer of the ECE using Redis. It provides both exact match caching and semantic (vector-based) caching to reduce latency and prepare the system for the real-time InjectorAgent.

## Features

- **Exact Match Caching**: Store and retrieve data using exact key matches
- **Semantic Caching**: Store and retrieve data using vector similarity search
- **Cache Eviction**: Implement cache eviction policies (LRU, TTL)
- **Cache Statistics**: Track cache performance metrics
- **High Performance**: Optimized for low-latency operations
- **Scalability**: Designed to handle high throughput

## API Endpoints

### Store Cache Entry
- **Endpoint**: `/cache/store`
- **Method**: POST
- **Request Body**: 
  ```json
  {
    "key": "unique_identifier",
    "value": "cached_value",
    "embedding": [0.1, 0.2, 0.3], // Optional vector embedding
    "ttl": 3600 // Optional time to live in seconds
  }
  ```
- **Response**: Confirmation of storage operation

### Retrieve Cache Entry
- **Endpoint**: `/cache/retrieve`
- **Method**: POST
- **Request Body**: 
  ```json
  {
    "key": "unique_identifier"
  }
  ```
- **Response**: 
  ```json
  {
    "key": "unique_identifier",
    "value": "cached_value"
  }
  ```

### Semantic Search
- **Endpoint**: `/cache/semantic_search`
- **Method**: POST
- **Request Body**: 
  ```json
  {
    "query_embedding": [0.1, 0.2, 0.3],
    "threshold": 0.8
  }
  ```
- **Response**: List of similar cache entries

### Cache Statistics
- **Endpoint**: `/cache/stats`
- **Method**: GET
- **Response**: 
  ```json
  {
    "hits": 100,
    "misses": 50,
    "hit_rate": 0.67,
    "size": 150,
    "max_size": 10000
  }
  ```

### Clear Cache
- **Endpoint**: `/cache/clear`
- **Method**: POST
- **Request Body**: 
  ```json
  {
    "pattern": "optional_pattern" // Optional pattern for selective clearing
  }
  ```
- **Response**: Confirmation of clearing operation

## Chat Interface

The CacheManager can also be accessed through the main chat interface by using keywords like "cache", "retrieve", "store in cache", "cached", or "memory cache" in your message.

Example:
```
User: "cache this information with key 'user_profile_123'"
Context: {
  "cache_action": "store",
  "cache_key": "user_profile_123",
  "cache_value": "{\"name\": \"John Doe\", \"age\": 30}",
  "cache_embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
}
```

## Data Models

### CacheEntry
```json
{
  "key": "unique_identifier",
  "value": "cached_value",
  "embedding": [0.1, 0.2, 0.3], // Optional vector embedding
  "created_at": "2023-01-01T00:00:00Z",
  "expires_at": "2023-01-01T01:00:00Z", // Optional expiration time
  "access_count": 5
}
```

### SemanticQuery
```json
{
  "text": "query text",
  "embedding": [0.1, 0.2, 0.3],
  "threshold": 0.8
}
```

### CacheStats
```json
{
  "hits": 100,
  "misses": 50,
  "hit_rate": 0.67,
  "size": 150,
  "max_size": 10000
}
```