"""Abstract Vector DB adapter interface for ECE_Core.

This module exposes a small interface to integrate vector DBs such as
Pinecone, Milvus, Redis Vector, or FAISS as a local embed store.

Implementations should be lightweight and provide a test-backed
in-memory FAISS-like adapter for unit tests.
"""
from __future__ import annotations
from typing import Protocol, List, Dict, Any, Optional, Tuple
from src.config import settings
from src.vector_adapters.redis_vector_adapter import RedisVectorAdapter
from src.vector_adapters.fake_vector_adapter import FakeVectorAdapter

class VectorAdapter(Protocol):
    """Vector DB abstraction layer."""

    async def index_chunk(self, embedding_id: str, node_id: str, chunk_index: int, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Index (or upsert) an embedding with metadata into the vector DB.

        embedding_id: unique ID for the vector entry
        node_id: Neo4j node id or external id
        chunk_index: index of the chunk within the content
        embedding: numeric embedding vector
        metadata: additional properties (raw text, timestamp)
        """

    async def query_vector(self, embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        """Query the vector DB and return a list of hit dicts with keys: score, embedding_id, node_id, chunk_index, metadata"""

    async def delete(self, embedding_id: str) -> None:
        """Delete an embedding by id."""

    async def get(self, embedding_id: str) -> Optional[Dict[str, Any]]:
        """Get a vector entry by id, returning scoreless metadata and mapping"""

    async def health(self) -> bool:
        """Return health check boolean for adapter status."""

    async def initialize(self) -> None:
        """Optional initialization for the adapter (e.g. connect to Redis)."""


def create_vector_adapter(adapter_name: str | None = None) -> VectorAdapter:
    """Factory to create a vector adapter by name.
    Defaults to a Redis-backed adapter when `redis` is requested. Falls back
    to a memory-backed adapter (RedisVectorAdapter's in-memory mode) if Redis
    isn't available.
    """
    name = adapter_name or getattr(settings, "vector_adapter_name", "redis")
    if name == "redis":
        adapter = RedisVectorAdapter(redis_url=settings.redis_url)
        return adapter
    if name == "fake":
        return FakeVectorAdapter()
    # fallback to redis-based adapter which supports in-memory fallback
    adapter = RedisVectorAdapter(redis_url=settings.redis_url)
    return adapter
