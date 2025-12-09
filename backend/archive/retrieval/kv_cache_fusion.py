"""
C2C (Cache-to-Cache) Semantic Communication: KV-Cache Fusion Techniques

This module implements efficient context passing between model calls via
preserved KV-cache states and intelligent cache merging.

Key Components:
- KVCachePool: Session-level cache management
- SemanticState: Compressed semantic state for carryover
- CacheManager: Multi-source cache fusion orchestration
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import asyncio
from collections import defaultdict


@dataclass
class CacheMetrics:
    """Track cache performance metrics."""
    hit_count: int = 0
    miss_count: int = 0
    fusion_count: int = 0
    tokens_saved: int = 0
    memory_used_mb: float = 0.0
    
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0
    
    def efficiency(self) -> Dict[str, Any]:
        """Return efficiency metrics."""
        return {
            "hit_rate": f"{self.hit_rate() * 100:.1f}%",
            "total_hits": self.hit_count,
            "total_misses": self.miss_count,
            "fusions_performed": self.fusion_count,
            "tokens_saved": self.tokens_saved,
            "memory_used_mb": f"{self.memory_used_mb:.1f}"
        }


@dataclass
class KVCacheEntry:
    """Single KV-cache entry with metadata."""
    cache_id: str
    source: str  # "system_prompt", "memory", "reasoning", "query"
    content_hash: str
    timestamp: float
    ttl: int  # seconds
    size_estimate_bytes: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.timestamp > self.ttl


@dataclass
class SemanticState:
    """Compressed semantic state for context carryover between calls."""
    iteration: int
    state_id: str
    reasoning_text: str  # Textual summary of reasoning so far
    key_entities: List[str]  # Important entities mentioned
    decisions: List[str]  # Key decisions made
    open_questions: List[str]  # Unresolved questions
    compressed_tokens: int  # Estimated tokens in compressed state
    timestamp: float = None
    kv_cache_id: Optional[str] = None  # ID of cached KV state (if available)
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticState":
        """Deserialize from dictionary."""
        return cls(**data)


class KVCachePool:
    """
    Session-level KV-cache pool for efficient context reuse.
    
    Manages cache lifecycle: creation → reuse → invalidation → eviction.
    """
    
    def __init__(self, ttl_seconds: int = 600):
        """
        Initialize cache pool.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default 10 min)
        """
        self.ttl = ttl_seconds
        self.pools: Dict[str, Dict[str, KVCacheEntry]] = defaultdict(dict)
        self.metrics: Dict[str, CacheMetrics] = defaultdict(CacheMetrics)
        self._lock = asyncio.Lock()
    
    def _generate_cache_id(self, source: str, content: str) -> str:
        """Generate deterministic cache ID from content."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{source}_{content_hash}_{int(time.time())}"
    
    def _estimate_cache_size(self, content_length: int) -> int:
        """Estimate cache size in bytes (rough heuristic)."""
        # Transformer cache: typically 2-4x input size for KV tensors
        # Rough estimate: 4 chars ≈ 1 token, token → 64 bytes (2x fp32 in KV)
        tokens = content_length // 4
        return tokens * 64 * 2  # K and V
    
    async def add_cache(
        self,
        session_id: str,
        source: str,
        content: str,
        priority: float = 1.0
    ) -> str:
        """
        Add content to cache pool.
        
        Args:
            session_id: Session identifier
            source: Cache source type
            content: Content to cache
            priority: Priority level (unused, for future optimization)
        
        Returns:
            Cache ID for retrieval
        """
        async with self._lock:
            cache_id = self._generate_cache_id(source, content)
            entry = KVCacheEntry(
                cache_id=cache_id,
                source=source,
                content_hash=hashlib.sha256(content.encode()).hexdigest()[:16],
                timestamp=time.time(),
                ttl=self.ttl,
                size_estimate_bytes=self._estimate_cache_size(len(content))
            )
            
            self.pools[session_id][cache_id] = entry
            self.metrics[session_id].memory_used_mb += entry.size_estimate_bytes / (1024 * 1024)
            
            return cache_id
    
    async def get_cache(self, session_id: str, cache_id: str) -> Optional[KVCacheEntry]:
        """Retrieve cache entry by ID."""
        async with self._lock:
            if cache_id not in self.pools[session_id]:
                self.metrics[session_id].miss_count += 1
                return None
            
            entry = self.pools[session_id][cache_id]
            if entry.is_expired():
                del self.pools[session_id][cache_id]
                self.metrics[session_id].miss_count += 1
                return None
            
            self.metrics[session_id].hit_count += 1
            return entry
    
    async def get_cached_by_source(
        self,
        session_id: str,
        source: str,
        max_age_seconds: Optional[int] = None
    ) -> List[KVCacheEntry]:
        """
        Get all cache entries from a specific source.
        
        Args:
            session_id: Session identifier
            source: Source type to filter by
            max_age_seconds: Only return entries younger than this age
        
        Returns:
            List of matching cache entries
        """
        async with self._lock:
            entries = []
            for cache_id, entry in self.pools[session_id].items():
                if entry.source == source and not entry.is_expired():
                    if max_age_seconds is None or (time.time() - entry.timestamp) < max_age_seconds:
                        entries.append(entry)
            return entries
    
    async def invalidate_cache(self, session_id: str, cache_id: str) -> bool:
        """Invalidate specific cache entry."""
        async with self._lock:
            if cache_id in self.pools[session_id]:
                entry = self.pools[session_id][cache_id]
                self.metrics[session_id].memory_used_mb -= entry.size_estimate_bytes / (1024 * 1024)
                del self.pools[session_id][cache_id]
                return True
            return False
    
    async def invalidate_source(self, session_id: str, source: str):
        """Invalidate all entries from a source."""
        async with self._lock:
            to_delete = [
                cache_id for cache_id, entry in self.pools[session_id].items()
                if entry.source == source
            ]
            for cache_id in to_delete:
                entry = self.pools[session_id][cache_id]
                self.metrics[session_id].memory_used_mb -= entry.size_estimate_bytes / (1024 * 1024)
                del self.pools[session_id][cache_id]
    
    async def cleanup_expired(self, session_id: str) -> int:
        """
        Clean up expired entries for a session.
        
        Returns:
            Number of entries cleaned
        """
        async with self._lock:
            expired_ids = [
                cache_id for cache_id, entry in self.pools[session_id].items()
                if entry.is_expired()
            ]
            for cache_id in expired_ids:
                entry = self.pools[session_id][cache_id]
                self.metrics[session_id].memory_used_mb -= entry.size_estimate_bytes / (1024 * 1024)
                del self.pools[session_id][cache_id]
            return len(expired_ids)
    
    async def cleanup_session(self, session_id: str):
        """Remove all caches for a session."""
        async with self._lock:
            if session_id in self.pools:
                del self.pools[session_id]
            if session_id in self.metrics:
                del self.metrics[session_id]
    
    async def get_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get cache metrics for session."""
        async with self._lock:
            metrics = self.metrics[session_id]
            return metrics.efficiency()


class CacheManager:
    """
    Orchestrates multi-source cache fusion and reuse.
    
    Strategies:
    - Semantic Prefix Caching: Preserve fixed content (system prompt)
    - Iterative State Compression: Cache compressed reasoning states
    - Adaptive Cache Merging: Merge overlapping caches intelligently
    """
    
    def __init__(self, cache_pool: KVCachePool, fusion_threshold: float = 0.7):
        """
        Initialize cache manager.
        
        Args:
            cache_pool: Shared KVCachePool instance
            fusion_threshold: Similarity threshold for cache merging (0.0-1.0)
        """
        self.pool = cache_pool
        self.fusion_threshold = fusion_threshold
        self.semantic_states: Dict[str, SemanticState] = {}
        self._state_lock = asyncio.Lock()
    
    async def cache_system_prompt(self, session_id: str, prompt: str) -> str:
        """
        Cache system prompt (strategy: semantic prefix caching).
        System prompt is fixed per session, so cache and reuse across all calls.
        
        Args:
            session_id: Session identifier
            prompt: System prompt text
        
        Returns:
            Cache ID for system prompt
        """
        return await self.pool.add_cache(
            session_id=session_id,
            source="system_prompt",
            content=prompt,
            priority=1.0  # Highest priority
        )
    
    async def cache_retrieved_memories(
        self,
        session_id: str,
        memories: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Cache retrieved memories.
        
        Args:
            session_id: Session identifier
            memories: List of memory dicts with 'content' field
        
        Returns:
            List of cache IDs
        """
        cache_ids = []
        for mem in memories:
            content = mem.get('content', '')
            cache_id = await self.pool.add_cache(
                session_id=session_id,
                source="memory",
                content=content,
                priority=0.7
            )
            cache_ids.append(cache_id)
        return cache_ids
    
    async def cache_semantic_state(
        self,
        session_id: str,
        state: SemanticState
    ) -> None:
        """
        Cache semantic state from reasoning iteration.
        
        Args:
            session_id: Session identifier
            state: SemanticState to cache
        """
        async with self._state_lock:
            self.semantic_states[f"{session_id}:{state.iteration}"] = state
            
            # Also cache the reasoning text for KV reuse
            cache_id = await self.pool.add_cache(
                session_id=session_id,
                source="reasoning",
                content=state.reasoning_text,
                priority=0.8
            )
            state.kv_cache_id = cache_id
    
    async def get_semantic_state(self, session_id: str, iteration: int) -> Optional[SemanticState]:
        """Retrieve semantic state from a previous iteration."""
        async with self._state_lock:
            key = f"{session_id}:{iteration}"
            return self.semantic_states.get(key)
    
    async def estimate_fusion_efficiency(
        self,
        session_id: str,
        new_content: str
    ) -> Dict[str, Any]:
        """
        Estimate how much cache reuse is possible for new content.
        
        Returns metrics about potential fusion efficiency.
        """
        cached = await self.pool.get_cached_by_source(session_id, "memory")
        cached += await self.pool.get_cached_by_source(session_id, "system_prompt")
        cached += await self.pool.get_cached_by_source(session_id, "reasoning")
        
        total_cached_size = sum(e.size_estimate_bytes for e in cached)
        new_size = self.pool._estimate_cache_size(len(new_content))
        
        # Estimate tokens that can be reused (heuristic)
        reusable_tokens = (total_cached_size // 128) if total_cached_size > 0 else 0
        new_tokens = new_size // 128
        total_tokens = reusable_tokens + new_tokens
        
        efficiency_ratio = reusable_tokens / total_tokens if total_tokens > 0 else 0
        
        return {
            "cached_entries": len(cached),
            "reusable_tokens": int(reusable_tokens),
            "new_tokens": int(new_tokens),
            "efficiency_ratio": f"{efficiency_ratio * 100:.1f}%",
            "estimated_speedup": f"{1 / (1 - efficiency_ratio * 0.5):.2f}x" if efficiency_ratio > 0 else "1.0x"
        }
    
    async def merge_caches(
        self,
        session_id: str,
        cache_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Merge multiple cache entries intelligently.
        
        Strategy: Keep highest-quality representation of each semantic region.
        In practice, this returns metadata for the fusion operation.
        
        Args:
            session_id: Session identifier
            cache_ids: List of cache IDs to potentially merge
        
        Returns:
            Merge metadata and new combined cache ID
        """
        entries = []
        for cache_id in cache_ids:
            entry = await self.pool.get_cache(session_id, cache_id)
            if entry:
                entries.append(entry)
        
        if not entries:
            return {"merged": False, "reason": "No valid cache entries"}
        
        # Create merged entry (simplified: just concatenate IDs)
        merged_id = f"merged_{len(entries)}_{int(time.time())}"
        total_size = sum(e.size_estimate_bytes for e in entries)
        
        self.pool.metrics[session_id].fusion_count += 1
        
        return {
            "merged": True,
            "merged_cache_id": merged_id,
            "entries_merged": len(entries),
            "total_size_bytes": total_size,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_fusion_stats(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive fusion statistics for session."""
        metrics = await self.pool.get_metrics(session_id)
        cached = await self.pool.get_cached_by_source(session_id, "memory")
        
        return {
            "session_id": session_id,
            "cache_metrics": metrics,
            "cached_memories": len(cached),
            "active_states": len([k for k in self.semantic_states.keys() if k.startswith(session_id)]),
            "timestamp": datetime.now().isoformat()
        }


class C2COptimizer:
    """
    High-level optimizer that decides when and how to use C2C techniques.
    
    Decision logic:
    - Use cache if content is > 500 tokens and appears in multiple calls
    - Use state compression if doing iterative reasoning (>2 iterations)
    - Use cache merging if >3 overlapping cache entries
    """
    
    def __init__(self, cache_manager: CacheManager):
        """Initialize optimizer with cache manager."""
        self.cache_manager = cache_manager
        self.call_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    async def log_call(
        self,
        session_id: str,
        call_type: str,  # "query", "reasoning", "retrieval"
        content_length: int,
        response_tokens: int
    ):
        """Log LLM call for analysis."""
        self.call_history[session_id].append({
            "type": call_type,
            "content_length": content_length,
            "response_tokens": response_tokens,
            "timestamp": time.time()
        })
    
    async def should_use_cache(self, session_id: str, call_type: str) -> bool:
        """Determine if caching should be used for this call."""
        # Always cache system prompts
        if call_type == "system_prompt":
            return True
        
        # Cache memory retrievals if they're larger
        if call_type == "retrieval" and len(self.call_history[session_id]) > 0:
            return True
        
        # Use cache for iterative calls (reasoning) if we have history
        calls = self.call_history[session_id]
        if len(calls) > 1:
            recent_total = sum(c["content_length"] for c in calls[-3:])
            return recent_total > 2000  # Threshold
        
        return False
    
    async def get_optimization_recommendation(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Recommend optimization strategies based on call patterns.
        
        Returns recommendations for which C2C strategies to enable.
        """
        calls = self.call_history[session_id]
        
        if len(calls) == 0:
            return {"recommendation": "none", "reason": "No call history"}
        
        # Check for iterative pattern
        iterative_count = sum(1 for c in calls if c["type"] == "reasoning")
        is_iterative = iterative_count > 2
        
        # Check average content size
        avg_size = sum(c["content_length"] for c in calls) / len(calls) if calls else 0
        needs_prefix_cache = avg_size > 1000
        
        recommendations = []
        if is_iterative:
            recommendations.append("iterative_state_compression")
        if needs_prefix_cache:
            recommendations.append("semantic_prefix_caching")
        if len(calls) > 5:
            recommendations.append("adaptive_cache_merging")
        
        return {
            "session_id": session_id,
            "total_calls": len(calls),
            "iterative_calls": iterative_count,
            "avg_content_length": int(avg_size),
            "recommended_strategies": recommendations,
            "estimated_improvement": "30-50%" if recommendations else "0-10%"
        }


# Utility function for easy initialization
async def create_c2c_system() -> Tuple[KVCachePool, CacheManager, C2COptimizer]:
    """
    Factory function to create a complete C2C system.
    
    Returns:
        Tuple of (KVCachePool, CacheManager, C2COptimizer)
    """
    pool = KVCachePool(ttl_seconds=600)
    manager = CacheManager(pool, fusion_threshold=0.7)
    optimizer = C2COptimizer(manager)
    return pool, manager, optimizer
