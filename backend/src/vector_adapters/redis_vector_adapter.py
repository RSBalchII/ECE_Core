"""Redis VectorAdapter implementation with an in-memory fallback.

This adapter stores embeddings in Redis as simple JSON-serialized fields
and performs similarity queries in-process when the Redis server doesn't
have RediSearch vector index capabilities. This keeps tests deterministic
and avoids requiring Redis modules in CI.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
import math
import json
import logging
import redis.asyncio as redis

logger = logging.getLogger(__name__)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class RedisVectorAdapter:
    """A lightweight Redis vector adapter.

    This adapter stores each vector entry under `vec:{embedding_id}`
    as a Redis hash with fields: embedding (JSON), node_id, chunk_index, metadata.
    During queries, it will enumerate the stored ids from a Redis set 'vec:index'
    and compute cosine similarity in Python if the server does not provide
    a vector-search capability.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        # Local in-memory fallback index when Redis is not available or for fast tests
        self._in_memory: Dict[str, Dict[str, Any]] = {}
        # RediSearch availability
        self._redis_search_available: bool = False
        self._index_created: bool = False
        self._vector_dim: Optional[int] = None

    async def initialize(self):
        try:
            self.client = await redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            logger.info("RedisVectorAdapter: connected to Redis")
            # Try to detect RediSearch FT API (client.ft exists) when using redis-py
            try:
                if hasattr(self.client, "ft"):
                    # Try to run a minimal info command for 'vec_index' to detect if there's a vector index
                    try:
                        await self.client.ft("vec_index").info()
                        self._redis_search_available = True
                        self._index_created = True
                    except Exception:
                        # Index does not exist; still mark search available because Redis supports FT API
                        self._redis_search_available = True
                        self._index_created = False
            except Exception:
                self._redis_search_available = False
        except Exception as e:
            logger.warning(f"RedisVectorAdapter: unable to connect redis: {e}. Using in-memory fallback.")
            self.client = None

    async def index_chunk(self, embedding_id: str, node_id: str, chunk_index: int, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "embedding": embedding,
            "node_id": node_id,
            "chunk_index": chunk_index,
            "metadata": metadata or {}
        }
        if self.client:
            try:
                key = f"vec:{embedding_id}"
                # Store embedding as JSON by default
                await self.client.hset(key, mapping={
                    "embedding": json.dumps(embedding),
                    "node_id": node_id,
                    "chunk_index": chunk_index,
                    "metadata": json.dumps(metadata or {})
                })
                await self.client.sadd("vec:index", embedding_id)
                # Create RediSearch vector index if available and not yet created
                if self._redis_search_available and not self._index_created:
                    try:
                        # Determine vector dimension from embedding
                        dim = len(embedding)
                        self._vector_dim = dim
                        # Try to create an index with a simple HNSW vector field. Use dialect 2 compatibility.
                        # Try both mechanisms: explicit execute_command or ft().create depending on redis client
                        try:
                            await self.client.execute_command(
                                "FT.CREATE",
                                "vec_index",
                                "ON",
                                "HASH",
                                "PREFIX",
                                "1",
                                "vec:",
                                "SCHEMA",
                                "embedding",
                                "VECTOR",
                                "HNSW",
                                "6",
                                "TYPE",
                                "FLOAT32",
                                "DIM",
                                str(dim),
                                "DISTANCE_METRIC",
                                "COSINE",
                            )
                        except Exception:
                            # Try the high-level API if available
                            try:
                                if hasattr(self.client, "ft") and hasattr(self.client.ft("vec_index"), "create"):
                                    if hasattr(self.client.ft("vec_index"), "create"):
                                        # Some redis clients have 'create' on ft object; attempt to call
                                        await self.client.ft("vec_index").create(
                                            [
                                                ("embedding", {"TYPE": "VECTOR", "ALGORITHM": "HNSW", "TYPE_PARAMS": {"TYPE": "FLOAT32", "DIM": dim, "DISTANCE_METRIC": "COSINE"}})
                                            ]
                                        )
                            except Exception as e2:
                                logger.info(f"RedisVectorAdapter: failed to create RediSearch index via execute or high-level API: {e2}")
                        self._index_created = True
                    except Exception as e:
                        logger.info(f"RedisVectorAdapter: failed to create RediSearch index: {e}")
                return
            except Exception as e:
                logger.warning(f"RedisVectorAdapter: Redis write failed: {e}")

        # Fallback to in-memory storage
        self._in_memory[embedding_id] = entry

    async def query_vector(self, embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        candidates = []
        # If redis is present, enumerate ids in the set and HGET each one
        if self.client:
            try:
                # If RediSearch is available and index is created, use FT.SEARCH
                if self._redis_search_available and self._index_created and hasattr(self.client, "ft"):
                    try:
                        # Use redispy's FT API if available; pack float32 bytes as $vec_param
                        import struct

                        if isinstance(embedding, list):
                            vec_bytes = struct.pack(f"{len(embedding)}f", *embedding)
                        else:
                            vec_bytes = embedding

                        # Compose a KNN vector search query
                        query = f"*=>[KNN {top_k} @embedding $vec_param AS score]"

                        # Try high-level ft().search first
                        if hasattr(self.client, "ft") and hasattr(self.client.ft("vec_index"), "search"):
                            res = await self.client.ft("vec_index").search(query, query_params={"vec_param": vec_bytes})
                            for doc in getattr(res, "docs", []):
                                fields = getattr(doc, "__dict__", {})
                                score = float(getattr(doc, "score", 0.0))
                                candidates.append({
                                    "score": float(score),
                                    "embedding_id": str(doc.id).replace("vec:", ""),
                                    "node_id": getattr(doc, "node_id", None) or fields.get("node_id"),
                                    "chunk_index": int(getattr(doc, "chunk_index", 0) or fields.get("chunk_index", 0)),
                                    "metadata": json.loads(getattr(doc, "metadata", "{}") or fields.get("metadata", "{}")),
                                })
                            candidates.sort(key=lambda x: x["score"], reverse=True)
                            return candidates[:top_k]
                        else:
                            # Fallback to execute_command FT.SEARCH with PARAMS
                            try:
                                # FT.SEARCH vec_index query PARAMS 2 vec_param <bytes> DIALECT 2
                                res = await self.client.execute_command("FT.SEARCH", "vec_index", query, "PARAMS", 2, "vec_param", vec_bytes, "DIALECT", 2)
                                # res is a list; parse accordingly: [total, docId1, {fields}, docId2,...]
                                if isinstance(res, list) and len(res) >= 1:
                                    it = iter(res[1:])
                                    while True:
                                        try:
                                            docId = next(it)
                                        except StopIteration:
                                            break
                                        fields = next(it)
                                        score = 1.0
                                        # fields is a dict mapping field to value
                                        docid_str = str(docId)
                                        candidates.append({
                                            "score": float(score),
                                            "embedding_id": docid_str.replace("vec:", ""),
                                            "node_id": fields.get(b"node_id" if isinstance(fields, dict) else "node_id"),
                                            "chunk_index": int(fields.get(b"chunk_index", 0) if isinstance(fields, dict) else fields.get("chunk_index", 0)),
                                            "metadata": json.loads(fields.get(b"metadata", b"{}").decode() if isinstance(fields, dict) and isinstance(fields.get(b"metadata"), bytes) else (fields.get("metadata") or "{}")),
                                        })
                                    candidates.sort(key=lambda x: x["score"], reverse=True)
                                    return candidates[:top_k]
                            except Exception as e:
                                logger.info(f"RedisVectorAdapter: execute FT.SEARCH failed: {e}")
                    except Exception as e:
                        logger.info(f"RedisVectorAdapter: RediSearch query failed, fallback: {e}")
                        # If we got results, return top_k
                        candidates.sort(key=lambda x: x["score"], reverse=True)
                        return candidates[:top_k]
                    except Exception as e:
                        logger.info(f"RedisVectorAdapter: RediSearch query failed, fallback: {e}")
                        # Fall back to scanning members
                ids = await self.client.smembers("vec:index")
                for eid in ids:
                    key = f"vec:{eid}"
                    data = await self.client.hgetall(key)
                    if not data:
                        continue
                    try:
                        emb = json.loads(data.get("embedding"))
                        node_id = data.get("node_id")
                        chunk_index = int(data.get("chunk_index", 0))
                        metadata = json.loads(data.get("metadata") or "{}")
                    except Exception:
                        continue
                    score = _cosine_similarity(embedding, emb)
                    candidates.append({
                        "score": float(score),
                        "embedding_id": eid,
                        "node_id": node_id,
                        "chunk_index": chunk_index,
                        "metadata": metadata,
                    })
            except Exception as e:
                logger.warning(f"RedisVectorAdapter: Redis read failed during query: {e}")
                # Fall through to in-memory fallback

        # In-memory candidate enumeration
        for eid, data in self._in_memory.items():
            try:
                score = _cosine_similarity(embedding, data["embedding"])
                candidates.append({
                    "score": float(score),
                    "embedding_id": eid,
                    "node_id": data["node_id"],
                    "chunk_index": int(data["chunk_index"]),
                    "metadata": data["metadata"],
                })
            except Exception:
                continue

        # Sort by score (descending) and return top_k
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]

    async def delete(self, embedding_id: str) -> None:
        if self.client:
            try:
                key = f"vec:{embedding_id}"
                await self.client.delete(key)
                await self.client.srem("vec:index", embedding_id)
                return
            except Exception as e:
                logger.warning(f"RedisVectorAdapter: Redis delete failed: {e}")

        self._in_memory.pop(embedding_id, None)

    async def get(self, embedding_id: str) -> Optional[Dict[str, Any]]:
        if self.client:
            try:
                key = f"vec:{embedding_id}"
                data = await self.client.hgetall(key)
                if not data:
                    return None
                emb = json.loads(data.get("embedding"))
                return {
                    "embedding_id": embedding_id,
                    "embedding": emb,
                    "node_id": data.get("node_id"),
                    "chunk_index": int(data.get("chunk_index", 0)),
                    "metadata": json.loads(data.get("metadata") or "{}")
                }
            except Exception as e:
                logger.warning(f"RedisVectorAdapter: Redis get failed: {e}")
                return None

        entry = self._in_memory.get(embedding_id)
        if not entry:
            return None
        return {
            "embedding_id": embedding_id,
            "embedding": entry["embedding"],
            "node_id": entry["node_id"],
            "chunk_index": int(entry["chunk_index"]),
            "metadata": entry["metadata"],
        }

    async def health(self) -> bool:
        if self.client:
            try:
                await self.client.ping()
                return True
            except Exception as e:
                logger.warning(f"RedisVectorAdapter: health ping failed: {e}")
                return False
        # In-memory fallback always healthy
        return True
