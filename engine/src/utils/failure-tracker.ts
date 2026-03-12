/**
 * Failure Metrics Tracking
 * 
 * Tracks operation failures across the system for monitoring and alerting.
 * Provides insights into recurring issues and system health.
 * 
 * Usage:
 *   failureTracker.record('search', error);
 *   const stats = failureTracker.getStats();
 */

export interface FailureRecord {
  operation: string;
  error: string;
  errorCode?: string;
  timestamp: number;
  context?: Record<string, any>;
}

export interface FailureStats {
  totalFailures: number;
  failuresByOperation: Map<string, number>;
  failuresByErrorCode: Map<string, number>;
  recentFailures: FailureRecord[];
  failureRate: number; // failures per minute (last 5 minutes)
  mostCommonErrors: Array<{ error: string; count: number }>;
}

export interface CircuitBreakerState {
  failures: number;
  lastFailureTime: number;
  state: 'closed' | 'open' | 'half-open';
  lastStateChange: number;
}

class FailureTracker {
  private maxRecentFailures = 100;
  private recentFailures: FailureRecord[] = [];
  private failureCounts = new Map<string, number>(); // operation -> count
  private errorCodeCounts = new Map<string, number>();
  private errorCounts = new Map<string, number>();
  private circuitBreakers = new Map<string, CircuitBreakerState>();
  
  // Circuit breaker configuration
  private readonly failureThreshold = 5; // failures before opening
  private readonly resetTimeoutMs = 60000; // 1 minute before half-open
  private readonly windowMs = 300000; // 5 minute window for rate calculation

  /**
   * Record a failure
   */
  record(
    operation: string,
    error: Error | string,
    options?: {
      errorCode?: string;
      context?: Record<string, any>;
    }
  ): void {
    const errorObj = error instanceof Error ? error : new Error(String(error));
    const errorCode = options?.errorCode || this.extractErrorCode(errorObj);
    
    const record: FailureRecord = {
      operation,
      error: errorObj.message,
      errorCode,
      timestamp: Date.now(),
      context: options?.context
    };

    // Add to recent failures
    this.recentFailures.push(record);
    if (this.recentFailures.length > this.maxRecentFailures) {
      this.recentFailures.shift();
    }

    // Update counts
    this.failureCounts.set(operation, (this.failureCounts.get(operation) || 0) + 1);
    
    if (errorCode) {
      this.errorCodeCounts.set(errorCode, (this.errorCodeCounts.get(errorCode) || 0) + 1);
    }

    this.errorCounts.set(errorObj.message, (this.errorCounts.get(errorObj.message) || 0) + 1);

    // Update circuit breaker
    this.updateCircuitBreaker(operation);

    // Log failure
    console.warn(`[FailureTracker] ${operation}: ${errorObj.message}${errorCode ? ` (${errorCode})` : ''}`);
  }

  /**
   * Record a successful operation (resets circuit breaker)
   */
  recordSuccess(operation: string): void {
    const breaker = this.circuitBreakers.get(operation);
    if (breaker && breaker.state === 'half-open') {
      breaker.state = 'closed';
      breaker.failures = 0;
      breaker.lastStateChange = Date.now();
      console.log(`[FailureTracker] Circuit breaker CLOSED for ${operation}`);
    }
  }

  /**
   * Check if operation should be allowed (circuit breaker)
   */
  isAllowed(operation: string): boolean {
    const breaker = this.circuitBreakers.get(operation);
    
    if (!breaker) {
      return true; // No breaker = closed (allowed)
    }

    if (breaker.state === 'closed') {
      return true;
    }

    if (breaker.state === 'open') {
      // Check if we should transition to half-open
      if (Date.now() - breaker.lastFailureTime >= this.resetTimeoutMs) {
        breaker.state = 'half-open';
        breaker.lastStateChange = Date.now();
        console.log(`[FailureTracker] Circuit breaker HALF-OPEN for ${operation}`);
        return true;
      }
      return false;
    }

    // Half-open: allow one request
    return true;
  }

  /**
   * Get failure statistics
   */
  getStats(): FailureStats {
    const now = Date.now();
    const recentWindow = this.recentFailures.filter(f => now - f.timestamp < this.windowMs);
    
    // Calculate failure rate (per minute)
    const failureRate = recentWindow.length / (this.windowMs / 60000);

    // Get most common errors
    const sortedErrors = Array.from(this.errorCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([error, count]) => ({ error, count }));

    return {
      totalFailures: this.recentFailures.length,
      failuresByOperation: new Map(this.failureCounts),
      failuresByErrorCode: new Map(this.errorCodeCounts),
      recentFailures: [...this.recentFailures],
      failureRate,
      mostCommonErrors: sortedErrors
    };
  }

  /**
   * Get circuit breaker state for an operation
   */
  getCircuitBreakerState(operation: string): CircuitBreakerState | undefined {
    return this.circuitBreakers.get(operation);
  }

  /**
   * Reset all tracked failures
   */
  reset(): void {
    this.recentFailures = [];
    this.failureCounts.clear();
    this.errorCodeCounts.clear();
    this.errorCounts.clear();
    this.circuitBreakers.clear();
  }

  /**
   * Reset failures for a specific operation
   */
  resetOperation(operation: string): void {
    this.failureCounts.delete(operation);
    this.circuitBreakers.delete(operation);
    
    // Remove from recent failures
    this.recentFailures = this.recentFailures.filter(f => f.operation !== operation);
  }

  /**
   * Extract error code from error message
   */
  private extractErrorCode(error: Error): string | undefined {
    // Try to extract common error patterns
    const message = error.message.toLowerCase();
    
    if (message.includes('timeout')) return 'TIMEOUT';
    if (message.includes('connection')) return 'CONNECTION_ERROR';
    if (message.includes('memory')) return 'MEMORY_ERROR';
    if (message.includes('permission') || message.includes('access')) return 'PERMISSION_ERROR';
    if (message.includes('not found')) return 'NOT_FOUND';
    if (message.includes('validation')) return 'VALIDATION_ERROR';
    if (message.includes('parse') || message.includes('syntax')) return 'PARSE_ERROR';
    
    return undefined;
  }

  /**
   * Update circuit breaker state
   */
  private updateCircuitBreaker(operation: string): void {
    let breaker = this.circuitBreakers.get(operation);
    
    if (!breaker) {
      breaker = {
        failures: 1,
        lastFailureTime: Date.now(),
        state: 'closed',
        lastStateChange: Date.now()
      };
    } else {
      breaker.failures++;
      breaker.lastFailureTime = Date.now();

      // Check if we should open the circuit
      if (breaker.failures >= this.failureThreshold && breaker.state === 'closed') {
        breaker.state = 'open';
        breaker.lastStateChange = Date.now();
        console.warn(`[FailureTracker] Circuit breaker OPEN for ${operation} (${breaker.failures} failures)`);
      }
    }

    this.circuitBreakers.set(operation, breaker);
  }
}

// Singleton instance
const globalFailureTracker = new FailureTracker();

export { globalFailureTracker as failureTracker };
export default FailureTracker;
