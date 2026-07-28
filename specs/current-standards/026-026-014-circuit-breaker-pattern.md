# Standard 014: Circuit Breaker Pattern

**Status:** Active  
**Date:** 2026-05-18  
**Priority:** P0 (Critical)  
**Category:** Robustness

## Problem

Service calls in Anchor Engine can fail due to:
- Network timeouts
- Database connection issues
- External API failures
- Resource exhaustion

Without protection, cascading failures can bring down the entire system. The circuit breaker pattern provides resilience by:
1. Preventing cascading failures
2. Allowing systems to recover
3. Providing clear failure tracking

## Solution

The circuit breaker pattern implements three states:

### Circuit States

| State | Description | Behavior |
|-------|-------------|----------|
| **Closed** | Normal operation | Requests pass through normally |
| **Open** | Failure threshold exceeded | Requests are rejected immediately |
| **Half-Open** | Recovery attempt | One request allowed to test recovery |

### State Transitions

```
┌─────────────┐     failureThreshold     ┌─────────────┐
│             │───────────────────────▶ │             │
│  CLOSED     │                         │   OPEN      │
│             │◀───────────────────────│             │
│  (on success)│                        │             │
└─────────────┘                         └─────────────┘
       │                                    │
       │         halfOpenTimeout            │
       │         (resetTimeout)              │
       ▼                                    ▼
┌─────────────┐                         ┌─────────────┐
│             │                         │             │
│  HALF-OPEN  │                         │   OPEN      │
│             │                         │             │
└─────────────┘                         └─────────────┘
     (one attempt)                    (remains open)
```

## Implementation

### CircuitBreaker Interface

```typescript
export interface CircuitBreaker {
  getState(): CircuitState;           // Returns current state
  recordSuccess(): void;              // Record successful call
  recordFailure(error?: Error): void; // Record failed call
  canExecute(): boolean;              // Can we make a call?
  execute<T>(fn: () => Promise<T>): Promise<T>; // Execute with protection
  getStats(): {
    totalCalls: number;
    successes: number;
    failures: number;
    currentState: CircuitState;
  };
}
```

### Configuration Options

```typescript
interface CircuitBreakerOptions {
  failureThreshold?: number;         // Failures before opening (default: 5)
  resetTimeout?: number;             // Time before half-open (default: 30s)
  halfOpenTimeout?: number;          // Time in half-open (default: 10s)
  enabled?: boolean;                 // Enable/disable circuit
  shouldFail?: (error: Error) => boolean; // Failure predicate
}
```

### Usage Example

```typescript
import { CircuitBreakerFactory } from './circuit-breaker';

// Create a circuit breaker for external API calls
const apiBreaker = CircuitBreakerFactory.createBreaker('external-api', {
  failureThreshold: 3,
  resetTimeout: 30000,
  halfOpenTimeout: 10000
});

// Use the circuit breaker
async function callExternalApi() {
  try {
    const result = await apiBreaker.execute(() => 
      fetchExternalApi()
    );
    return result;
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
}
```

## Failure Tracking

The `FailureTracker` records and categorizes failures:

```typescript
interface FailureTracker {
  recordFailure(type: string, error: Error, context?: Record<string, unknown>): void;
  getStats(): {
    totalFailures: number;
    failuresByType: Record<string, number>;
    recentFailures: Array<{
      type: string;
      error: string;
      context: Record<string, unknown>;
      timestamp: number;
    }>;
  };
  reset(): void;
}
```

### Failure Types

| Type | Description |
|------|-------------|
| `ConnectionError` | Network/connection failures |
| `TimeoutError` | Request timeouts |
| `ServiceError` | Service-specific errors |
| `MemoryPressure` | Memory-related failures |
| `DistillationError` | Distillation pipeline failures |
| `MCPError` | MCP server communication errors |

## Testing

P0 integration tests verify:
- Circuit opens after threshold failures
- Half-open transition after reset timeout
- Successful recovery closes the circuit
- Failure tracking by type
- Concurrent operation handling

See `engine/tests/integration/` for test implementations.

## Related Standards

- Standard 011: Security Hardening
- Standard 016: MCP Integration Testing
- Standard 028: Unified Test Pipeline

---

*Created: 2026-05-18*  
*Author: RS Balch II*