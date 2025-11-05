import redis
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.query import Query
from redis.commands.search.index_definition import IndexDefinition
import asyncio

from ece.agents.clients import ArchivistClient


@dataclass
class CacheEntry:
    """
    Data model for a cache entry.

    Attributes:
        key: The unique identifier for the cache entry.
        value: The text content of the context.
        embedding: Optional vector embedding of the content.
        created_at: Timestamp when the entry was created.
        access_count: Number of times the entry has been accessed.
    """

    key: str
    value: str
    embedding: Optional[List[float]] = None
    created_at: datetime = None
    access_count: int = 0

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class CacheManager:
    """
    A manager for the Redis-based Context Cache.

    This class provides methods to store, retrieve, and search for context entries
    in the Redis cache, managed by the Orchestrator agent.
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
        Initialize the CacheManager with Redis connection parameters.

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
                        # If no callback is provided, try to call the archivist client
                        # Use a background task approach to avoid 'asyncio.run() cannot be called from a running event loop' error
                        try:
                            # Try to get the running event loop
                            loop = asyncio.get_running_loop()
                            # If we're in a running loop, create a task
                            asyncio.create_task(
                                self.archivist_client.handle_truncated_entries(
                                    keys_to_delete
                                )
                            )
                        except RuntimeError:
                            # No running loop, so we can use asyncio.run() or just ignore for now
                            # For safety in sync contexts, we'll just print a warning instead of triggering the archivist
                            print(
                                f"Warning: Cache entries were trimmed but archivist client could not be notified asynchronously: {keys_to_delete}"
                            )
                    self.redis_client.delete(*keys_to_delete)
                    print(
                        f"Trimmed {len(keys_to_delete)} oldest entries from the cache."
                    )
        except Exception as e:
            print(f"Error trimming cache: {str(e)}")

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

    def store(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
        embedding: Optional[List[float]] = None,
    ) -> bool:
        """
        Store a key-value pair in the cache with an optional TTL and embedding.

        Args:
            key: The key to store the value under.
            value: The value to store.
            ttl: Time-to-live in seconds. If None, the key will not expire.
            embedding: Optional vector embedding of the content.

        Returns:
            True if the operation was successful, False otherwise.
        """
        try:
            # Use a prefix for the search index
            search_key = f"context_cache:{key}"

            # Store as a Redis hash
            mapping = {
                "value": value,
                "created_at": datetime.now().isoformat(),
                "access_count": 0,
            }

            if embedding:
                # Convert embedding to string for storage
                mapping["embedding"] = ",".join(map(str, embedding))

            if ttl:
                # Use pipeline for atomic operations with TTL
                pipe = self.redis_client.pipeline()
                pipe.hset(search_key, mapping=mapping)
                pipe.expire(search_key, ttl)
                pipe.execute()
            else:
                self.redis_client.hset(search_key, mapping=mapping)

            # Trim the cache if it exceeds max_size
            self._trim_cache()

            return True
        except Exception as e:
            print(f"Error storing key-value pair: {str(e)}")
            return False

    def retrieve(self, key: str) -> Optional[CacheEntry]:
        """
        Retrieve a value from the cache by its key.

        Args:
            key: The key to retrieve the value for.

        Returns:
            A CacheEntry object if the key exists, None otherwise.
        """
        try:
            # Use the prefixed key for retrieval
            search_key = f"context_cache:{key}"
            result = self.redis_client.hgetall(search_key)
            if not result:
                # Track cache miss
                self.redis_client.incr("cache_stats:misses")
                return None

            # Track cache hit
            self.redis_client.incr("cache_stats:hits")

            # Convert result to CacheEntry
            entry = CacheEntry(
                key=key,
                value=result.get("value", ""),
                created_at=datetime.fromisoformat(result.get("created_at"))
                if result.get("created_at")
                else None,
                access_count=int(result.get("access_count", 0)),
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
            self.redis_client.hincrby(search_key, "access_count", 1)

            return entry
        except Exception as e:
            print(f"Error retrieving value for key '{key}': {str(e)}")
            # Track as miss on error
            self.redis_client.incr("cache_stats:misses")
            return None

    def delete(self, key: str) -> bool:
        """
        Delete a key-value pair from the cache.

        Args:
            key: The key to delete.

        Returns:
            True if the key was deleted, False if the key did not exist.
        """
        try:
            # Use the prefixed key for deletion
            search_key = f"context_cache:{key}"
            result = self.redis_client.delete(search_key)
            return result > 0
        except Exception as e:
            print(f"Error deleting key '{key}': {str(e)}")
            return False

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

    def semantic_search(
        self, embedding: List[float], top_k: int = 5
    ) -> List[CacheEntry]:
        """
        Perform a vector similarity search using Redis Stack's capabilities.

        Args:
            embedding: The query vector embedding.
            top_k: The number of top similar results to return.

        Returns:
            A list of CacheEntry objects sorted by similarity.
        """
        try:
            # Get the search module
            search = self.redis_client.ft("context_cache_idx")

            # Convert embedding to bytes for search
            embedding_str = ",".join(map(str, embedding))

            # Create the query
            query = (
                Query(f"*=>[KNN {top_k} @embedding $vec AS distance]")
                .sort_by("distance")
                .return_fields(
                    "value", "created_at", "access_count", "embedding", "distance"
                )
                .dialect(2)
            )

            # Execute the query
            params = {"vec": embedding_str}
            results = search.search(query, query_params=params)

            # Convert results to CacheEntry objects
            entries = []
            for doc in results.docs:
                # Extract key from document id (removing prefix)
                key = doc.id.replace("context_cache:", "")

                entry = CacheEntry(
                    key=key,
                    value=getattr(doc, "value", ""),
                    created_at=datetime.fromisoformat(getattr(doc, "created_at", ""))
                    if getattr(doc, "created_at", None)
                    else None,
                    access_count=int(getattr(doc, "access_count", 0)),
                )

                # Handle embedding if present
                if hasattr(doc, "embedding"):
                    embedding_str = doc.embedding
                    entry.embedding = (
                        [float(x) for x in embedding_str.split(",")]
                        if embedding_str
                        else None
                    )

                entries.append(entry)

            return entries
        except Exception as e:
            print(f"Error performing semantic search: {str(e)}")
            return []

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
