"""A minimal fake vector adapter for unit tests.

This adapter stores embeddings in a local dictionary and performs cosine
similarity-based queries in Python. It's deterministic and suitable for
unit testing of vector-related behavior without requiring Redis or a
vector DB.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
import math
import logging

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


class FakeVectorAdapter:
    def __init__(self):
        self._index: Dict[str, Dict[str, Any]] = {}

    async def initialize(self):
        # No-op for fake
        return

    async def index_chunk(self, embedding_id: str, node_id: str, chunk_index: int, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        self._index[embedding_id] = {
            "embedding": embedding,
            "node_id": node_id,
            "chunk_index": chunk_index,
            "metadata": metadata or {}
        }

    async def query_vector(self, embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        candidates = []
        for eid, data in self._index.items():
            score = _cosine_similarity(embedding, data["embedding"]) if data.get("embedding") else 0.0
            candidates.append({
                "score": float(score),
                "embedding_id": eid,
                "node_id": data["node_id"],
                "chunk_index": data["chunk_index"],
                "metadata": data.get("metadata", {})
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]

    async def delete(self, embedding_id: str) -> None:
        self._index.pop(embedding_id, None)

    async def get(self, embedding_id: str) -> Optional[Dict[str, Any]]:
        return self._index.get(embedding_id)

    async def health(self) -> bool:
        return True
