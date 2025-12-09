"""
Circuit breaker pattern for ECE_Core external dependencies.
Prevents cascading failures when Neo4j or Redis are slow/down.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing - reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    
    Usage:
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        result = await breaker.call(my_async_function, arg1, arg2)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try resetting."""
        if self.last_failure_time is None:
            return True
        
        return datetime.now() > self.last_failure_time + timedelta(seconds=self.timeout)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception if circuit allows call
        """
        # If circuit is OPEN, check if we should try again
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerError("Circuit breaker is OPEN")
        
        try:
            # Attempt the call
            result = await func(*args, **kwargs)
            
            # Success - reset failure count
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                logger.info("Circuit breaker reset to CLOSED")
            
            self.failure_count = 0
            return result
        
        except self.expected_exception as e:
            # Track failure
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            logger.warning(f"Circuit breaker failure {self.failure_count}/{self.failure_threshold}: {e}")
            
            # Open circuit if threshold reached
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")
            
            raise

class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass

# ============================================================================
# PRE-CONFIGURED CIRCUIT BREAKERS
# ============================================================================

neo4j_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout=60,
    expected_exception=Exception
)

redis_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout=30,
    expected_exception=Exception
)

llm_breaker = CircuitBreaker(
    failure_threshold=10,
    timeout=120,
    expected_exception=Exception
)

# ============================================================================
# DECORATOR FOR EASY USAGE
# ============================================================================

def circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator to apply circuit breaker to async functions.
    
    Usage:
        @circuit_breaker(neo4j_breaker)
        async def query_neo4j(...):
            ...
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
