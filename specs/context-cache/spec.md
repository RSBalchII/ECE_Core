# Context Cache Specification

## Overview
The Context Cache is the short-term memory layer of the External Context Engine (ECE). It provides high-speed semantic and generative caching capabilities to reduce latency and prepare the system for the real-time InjectorAgent.

## Purpose
The Context Cache serves as an intermediary storage layer between the ECE's agents and the long-term knowledge graph. It enables:
1. Fast retrieval of recently accessed information
2. Semantic similarity search for related context
3. Reduced load on the Neo4j knowledge graph
4. Improved response times for repeated or similar queries

## Key Features
1. **Exact Match Caching**: Store and retrieve values by key
2. **Semantic Caching**: Store vector embeddings and perform similarity searches
3. **TTL Management**: Automatic expiration of cached entries
4. **Statistics Tracking**: Monitor cache performance (hit rate, size, etc.)
5. **Redis Integration**: Leverage Redis Stack for efficient storage and vector operations

## Data Models

### CacheEntry
Represents a single cached item:
- `key`: Unique identifier for the entry
- `value`: The cached data (string)
- `embedding`: Optional vector representation for semantic search
- `created_at`: Timestamp when entry was created
- `expires_at`: Timestamp when entry will expire
- `access_count`: Number of times entry has been accessed

### SemanticQuery
Represents a semantic search query:
- `text`: Query text
- `embedding`: Vector representation of the query
- `threshold`: Minimum similarity score for results

### CacheStats
Represents cache performance metrics:
- `hits`: Number of successful cache retrievals
- `misses`: Number of failed cache retrievals
- `hit_rate`: Ratio of hits to total requests
- `size`: Current number of entries in cache
- `max_size`: Maximum capacity of cache

## API Endpoints

### Cache Operations
- `POST /cache/store`: Store a value with optional embedding
- `POST /cache/retrieve`: Retrieve a value by key
- `POST /cache/semantic_search`: Find similar entries by embedding
- `GET /cache/stats`: Get cache performance statistics
- `POST /cache/clear`: Clear all cached entries

## Integration Points
- **Redis Stack**: Primary storage backend with vector similarity search
- **ExtractorAgent**: Populates cache with extracted information
- **InjectorAgent**: Consumes cached context for real-time injection
- **ArchivistAgent**: Long-term storage for cache eviction