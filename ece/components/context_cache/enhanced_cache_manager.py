#!/usr/bin/env python3
"""
Enhanced Context Cache Manager

This module extends the existing CacheManager with enhanced context functionality
specifically for the ECE Memory Management System.
"""

import redis
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.query import Query
from redis.commands.search.index_definition import IndexDefinition
import asyncio
import json

from ece.agents.clients import ArchivistClient


@dataclass
class EnhancedCacheEntry:
    """
    Enhanced data model for a cache entry with additional context information.

    Attributes:
        key: The unique identifier for the cache entry.
        value: The text content of the context.
        embedding: Optional vector embedding of the content.
        created_at: Timestamp when the entry was created.
        access_count: Number of times the entry has been accessed.
        session_id: Session identifier for tracking.
        context_type: Type of context (e.g., 'enhanced', 'related_memories', 'summary').
        metadata: Additional metadata about the context.
        token_count: Estimated token count of the content.
    """

    key: str
    value: str
    embedding: Optional[List[float]] = None
    created_at: datetime = None
    access_count: int = 0
    session_id: str = ""
    context_type: str = "general"
    metadata: Dict[str, Any] = None
    token_count: int = 0

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class EnhancedCacheManager:
    """
    Enhanced manager for the Redis-based Context Cache with support for
    the ECE Memory Management System's enhanced context requirements.

    This class extends the existing CacheManager with additional functionality
    for handling enhanced context, related memories, and token-aware caching.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        db: int = 0,
        vector_dimensions: int = 1536,
        max_size: int = 1000,
        truncation_callback: Optional[callable] = None,
    ):
        """
        Initialize the EnhancedCacheManager with Redis connection parameters.

        Args:
            host: Redis server host. Defaults to REDIS_HOST env var or 'localhost'.
            port: Redis server port. Defaults to REDIS_PORT env var or 6379.
            password: Redis password. Defaults to REDIS_PASSWORD env var.
            db: Redis database number. Defaults to 0.
            vector_dimensions: Dimensions of the vector embeddings. Defaults to 1536.
            max_size: Maximum number of entries in the cache. Defaults to 1000.
            truncation_callback: A function to call with the keys of truncated entries.
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.db = db
        self.vector_dimensions = vector_dimensions
        self.max_size = max_size
        self.truncation_callback = truncation_callback
        self.archivist_client = ArchivistClient()

        # Initialize Redis connection
        self.redis_client = self._connect()

        # Create search index if it doesn't exist
        self._create_search_index()

        # Initialize statistics
        self._init_statistics()

    def _connect(self) -> redis.Redis:
        """
        Establish a connection to the Redis instance.

        Returns:
            A Redis client instance.
        """
        try:
            client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                health_check_interval=30,
            )
            # Test the connection
            client.ping()
            return client
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {str(e)}")

    def _create_search_index(self):
        """
        Create a Redis search index for vector similarity search.
        """
        try:
            # Get the search module
            search = self.redis_client.ft("context_cache_idx")

            # Check if index already exists
            try:
                search.info()
                return  # Index already exists
            except:
                pass  # Index doesn't exist, create it

            # Define the schema for the search index
            schema = (
                TextField("value"),
                TextField("session_id"),
                TextField("context_type"),
                VectorField(
                    "embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.vector_dimensions,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            )

            # Create the index
            search.create_index(
                *schema,
                definition=IndexDefinition(
                    prefix=["context_cache:"], score_field="access_count"
                ),
            )
        except Exception as e:
            print(f"Warning: Could not create search index: {str(e)}")
            print("Semantic search may not be available.")

    def _init_statistics(self):
        """
        Initialize statistics tracking.
        """
        try:
            # Initialize counters if they don't exist
            if not self.redis_client.exists("cache_stats:hits"):
                self.redis_client.set("cache_stats:hits", 0)
            if not self.redis_client.exists("cache_stats:misses"):
                self.redis_client.set("cache_stats:misses", 0)
        except Exception as e:
            print(f"Warning: Could not initialize statistics: {str(e)}")

    def store_enhanced_context(
        self,
        session_id: str,
        enhanced_context: str,
        related_memories: Optional[List[Dict[str, Any]]] = None,
        ttl: Optional[int] = 3600,
    ) -> bool:
        """
        Store enhanced context and related memories in the cache for a session.

        Args:
            session_id: The session identifier
            enhanced_context: The enhanced context string
            related_memories: Optional list of related memories
            ttl: Time-to-live in seconds (default 1 hour)

        Returns:
            True if the operation was successful, False otherwise.
        """
        try:
            # Estimate token count for the enhanced context
            token_count = self._estimate_token_count(enhanced_context)

            # Store enhanced context
            context_key = f"context_cache:{session_id}:enhanced_context"
            context_entry = EnhancedCacheEntry(
                key=context_key,
                value=enhanced_context,
                session_id=session_id,
                context_type="enhanced_context",
                token_count=token_count,
                metadata={
                    "source": "archivist_qlearning_coordination",
                    "timestamp": datetime.now().isoformat(),
                },
            )

            success = self._store_entry(context_entry, ttl=ttl)

            if not success:
                print(f"Failed to store enhanced context for session {session_id}")
                return False

            # Store related memories if provided
            if related_memories:
                memories_key = f"context_cache:{session_id}:related_memories"
                memories_str = "n".join(
                    [mem.get("content", "") for mem in related_memories]
                )
                memories_token_count = self._estimate_token_count(memories_str)

                memories_entry = EnhancedCacheEntry(
                    key=memories_key,
                    value=memories_str,
                    session_id=session_id,
                    context_type="related_memories",
                    token_count=memories_token_count,
                    metadata={
                        "source": "archivist_qlearning_coordination",
                        "count": len(related_memories),
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                success = self._store_entry(memories_entry, ttl=ttl)

                if not success:
                    print(f"Failed to store related memories for session {session_id}")
                    # Don't fail completely if only memories failed
                    return True  # Still return True since context was stored

            print(f"✅ Stored enhanced context for session {session_id}")
            return True

        except Exception as e:
            print(f"Error storing enhanced context for session {session_id}: {str(e)}")
            return False

    def _estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).

        Args:
            text: Text to estimate token count for

        Returns:
            Estimated token count
        """
        # Rough approximation: 1.3 tokens per word
        word_count = len(text.split())
        return int(word_count * 1.3)

    def _store_entry(
        self, entry: EnhancedCacheEntry, ttl: Optional[int] = None
    ) -> bool:
        """
        Store an EnhancedCacheEntry in Redis.

        Args:
            entry: The EnhancedCacheEntry to store
            ttl: Time-to-live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert entry to Redis hash mapping
            mapping = {
                "value": entry.value,
                "created_at": entry.created_at.isoformat(),
                "access_count": entry.access_count,
                "session_id": entry.session_id,
                "context_type": entry.context_type,
                "token_count": entry.token_count,
                "metadata": json.dumps(entry.metadata) if entry.metadata else "{}",
            }

            if entry.embedding:
                # Convert embedding to string for storage
                mapping["embedding"] = ",".join(map(str, entry.embedding))

            if ttl:
                # Use pipeline for atomic operations with TTL
                pipe = self.redis_client.pipeline()
                pipe.hset(entry.key, mapping=mapping)
                pipe.expire(entry.key, ttl)
                pipe.execute()
            else:
                self.redis_client.hset(entry.key, mapping=mapping)

            # Trim the cache if it exceeds max_size
            self._trim_cache()

            return True
        except Exception as e:
            print(f"Error storing entry {entry.key}: {str(e)}")
            return False

    def _trim_cache(self):
        """
        Trim the cache to the max_size by removing the oldest entries.
        """
        try:
            # Get the number of keys in the cache
            num_keys = self.redis_client.dbsize()

            if num_keys > self.max_size:
                # Get all keys
                keys = self.redis_client.keys("context_cache:*")

                # Get creation times for all keys
                creation_times = []
                for key in keys:
                    created_at_str = self.redis_client.hget(key, "created_at")
                    if created_at_str:
                        creation_times.append(
                            (key, datetime.fromisoformat(created_at_str))
                        )

                # Sort keys by creation time (oldest first)
                creation_times.sort(key=lambda item: item[1])

                # Determine how many keys to delete
                num_to_delete = num_keys - self.max_size

                # Delete the oldest keys
                keys_to_delete = [item[0] for item in creation_times[:num_to_delete]]
                if keys_to_delete:
                    if self.truncation_callback:
                        self.truncation_callback(keys_to_delete)
                    else:
                        # If no callback is provided, call the archivist client
                        asyncio.run(
                            self.archivist_client.handle_truncated_entries(
                                keys_to_delete
                            )
                        )
                    self.redis_client.delete(*keys_to_delete)
                    print(
                        f"Trimmed {len(keys_to_delete)} oldest entries from the cache."
                    )
        except Exception as e:
            print(f"Error trimming cache: {str(e)}")

    def retrieve_enhanced_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve enhanced context and related memories for a session.

        Args:
            session_id: The session identifier

        Returns:
            Dictionary containing enhanced context and related memories, or None if not found
        """
        try:
            # Retrieve enhanced context
            context_key = f"context_cache:{session_id}:enhanced_context"
            context_entry = self._retrieve_entry(context_key)

            if not context_entry:
                print(f"No enhanced context found for session {session_id}")
                return None

            # Retrieve related memories
            memories_key = f"context_cache:{session_id}:related_memories"
            memories_entry = self._retrieve_entry(memories_key)

            result = {
                "enhanced_context": context_entry.value,
                "related_memories": [],
                "session_id": session_id,
                "timestamp": context_entry.created_at.isoformat()
                if context_entry.created_at
                else "",
                "access_count": context_entry.access_count,
                "token_count": context_entry.token_count,
            }

            if memories_entry and memories_entry.value:
                # Split memories by newline
                memories = memories_entry.value.split("n")
                result["related_memories"] = [
                    {"content": mem} for mem in memories if mem.strip()
                ]

            print(f"✅ Retrieved enhanced context for session {session_id}")
            return result

        except Exception as e:
            print(
                f"Error retrieving enhanced context for session {session_id}: {str(e)}"
            )
            return None

    def _retrieve_entry(self, key: str) -> Optional[EnhancedCacheEntry]:
        """
        Retrieve an EnhancedCacheEntry from Redis by key.

        Args:
            key: The key to retrieve

        Returns:
            EnhancedCacheEntry if found, None otherwise
        """
        try:
            result = self.redis_client.hgetall(key)
            if not result:
                # Track cache miss
                self.redis_client.incr("cache_stats:misses")
                return None

            # Track cache hit
            self.redis_client.incr("cache_stats:hits")

            # Convert result to EnhancedCacheEntry
            entry = EnhancedCacheEntry(
                key=key,
                value=result.get("value", ""),
                created_at=datetime.fromisoformat(result.get("created_at"))
                if result.get("created_at")
                else None,
                access_count=int(result.get("access_count", 0)),
                session_id=result.get("session_id", ""),
                context_type=result.get("context_type", "general"),
                token_count=int(result.get("token_count", 0)),
                metadata=json.loads(result.get("metadata", "{}"))
                if result.get("metadata")
                else {},
            )

            # Handle embedding if present
            if "embedding" in result:
                embedding_str = result["embedding"]
                entry.embedding = (
                    [float(x) for x in embedding_str.split(",")]
                    if embedding_str
                    else None
                )

            # Increment access count
            self.redis_client.hincrby(key, "access_count", 1)

            return entry
        except Exception as e:
            print(f"Error retrieving entry {key}: {str(e)}")
            # Track as miss on error
            self.redis_client.incr("cache_stats:misses")
            return None

    def get_context_aware_prompt(self, session_id: str, user_prompt: str) -> str:
        """
        Get a context-aware prompt that combines enhanced context with the user's prompt.

        Args:
            session_id: The session identifier
            user_prompt: The user's original prompt

        Returns:
            Context-aware prompt combining enhanced context and user prompt
        """
        try:
            # Retrieve enhanced context for the session
            context_data = self.retrieve_enhanced_context(session_id)

            if not context_data:
                print(
                    f"No enhanced context found for session {session_id}, returning original prompt"
                )
                return user_prompt

            enhanced_context = context_data.get("enhanced_context", "")
            related_memories = context_data.get("related_memories", [])

            if not enhanced_context:
                print(
                    f"Empty enhanced context for session {session_id}, returning original prompt"
                )
                return user_prompt

            # Create a context-aware prompt
            context_aware_prompt = f"""[CONTEXT]
{enhanced_context}

[RELATED MEMORIES]
{chr(10).join([f"- {mem.get('content', '')}" for mem in related_memories[:5]])}

[USER PROMPT]
{user_prompt}

Please consider the above context and related memories when responding to the user's prompt. 
The context contains relevant information that should inform your response. 
Read the context carefully before formulating your answer."""

            print(f"✅ Created context-aware prompt for session {session_id}")
            return context_aware_prompt

        except Exception as e:
            print(
                f"Error creating context-aware prompt for session {session_id}: {str(e)}"
            )
            # Fallback to original prompt
            return user_prompt

    def get_statistics(self) -> Dict[str, int]:
        """
        Get cache statistics including hits and misses.

        Returns:
            A dictionary containing cache statistics.
        """
        try:
            hits = int(self.redis_client.get("cache_stats:hits") or 0)
            misses = int(self.redis_client.get("cache_stats:misses") or 0)
            total = hits + misses
            hit_rate = hits / total if total > 0 else 0

            return {
                "hits": hits,
                "misses": misses,
                "total_requests": total,
                "hit_rate": hit_rate,
            }
        except Exception as e:
            print(f"Error getting cache statistics: {str(e)}")
            return {"hits": 0, "misses": 0, "total_requests": 0, "hit_rate": 0}

    def reset_statistics(self):
        """
        Reset cache statistics counters.
        """
        try:
            self.redis_client.set("cache_stats:hits", 0)
            self.redis_client.set("cache_stats:misses", 0)
        except Exception as e:
            print(f"Error resetting cache statistics: {str(e)}")

    def get_all_entries(self) -> Dict[str, str]:
        """
        Get all entries from the cache.

        Returns:
            A dictionary containing all cache entries.
        """
        try:
            # Get all keys with the context_cache prefix
            keys = self.redis_client.keys("context_cache:*")

            # Retrieve all entries
            entries = {}
            for key in keys:
                result = self.redis_client.hgetall(key)
                if result:
                    # Remove the prefix from the key for the returned dictionary
                    clean_key = key.replace("context_cache:", "")
                    entries[clean_key] = result.get("value", "")

            return entries
        except Exception as e:
            print(f"Error getting all cache entries: {str(e)}")
            return {}
