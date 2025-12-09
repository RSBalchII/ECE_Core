import redis.asyncio as redis
import logging
import time
from typing import Optional
from src.config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    """Handles Redis interactions for TieredMemory."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self.redis = None

    async def initialize(self):
        """Connect to Redis."""
        try:
            maybe_client = redis.from_url(self.redis_url, decode_responses=True)
            if hasattr(maybe_client, "__await__"):
                self.redis = await maybe_client
            else:
                self.redis = maybe_client
            
            ping_ret = self.redis.ping()
            if hasattr(ping_ret, "__await__"):
                await ping_ret
            logger.info("Redis connected")
        except redis.ConnectionError as e:
            logger.warning(f"Redis unavailable: {e}")
            self.redis = None
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.redis = None

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            try:
                await self.redis.close()
            except Exception:
                pass

    async def get_active_context(self, session_id: str) -> str:
        """Get active context from Redis."""
        if not self.redis:
            return ""
        try:
            context = await self.redis.get(f"session:{session_id}:context")
            return context or ""
        except Exception as e:
            logger.error(f"Redis get failed for session {session_id}: {e}")
            return ""

    async def save_active_context(self, session_id: str, context: str):
        """Save active context to Redis with TTL."""
        if not self.redis:
            return
        try:
            await self.redis.set(f"session:{session_id}:context", context, ex=settings.redis_ttl)
            # Also set a last-active timestamp to help background tasks avoid interfering with active sessions
            try:
                await self.redis.set(f"session:{session_id}:last_active_at", int(time.time()), ex=settings.redis_ttl)
            except Exception:
                # Not critical; continue saving context even if last_active failed
                pass
        except Exception as e:
            logger.error(f"Redis set failed for session {session_id}: {e}")

    async def clear_session(self, session_id: str):
        """Completely remove a session's active context and metadata."""
        if not self.redis:
            return
        try:
            # Delete both the context text and the activity timestamp
            keys = [f"session:{session_id}:context", f"session:{session_id}:last_active_at"]
            await self.redis.delete(*keys)
            logger.info(f"Cleared Redis cache for session: {session_id}")
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {e}")
