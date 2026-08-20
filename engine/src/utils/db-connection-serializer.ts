/**
 * Database Connection Serializer (v5.2.0+)
 *
 * PGlite is a single-connection WASM database. Concurrent db.run() calls corrupt
 * connection state → "cannot drop active portal" errors, deadlocks, silent data loss.
 *
 * This module provides a FIFO queue that serializes ALL database operations through
 * a single async channel. Queries are queued and executed one at a time in order.
 *
 * Architecture:
 *   Service A → db.run() ─┐
 *                          ├──→ [Connection Queue] → PGlite
 *   Service B → db.run() ─┘
 *
 * Key properties:
 * - FIFO ordering ensures deterministic execution
 * - In-flight tracking prevents queue overflow (rejects if >50 pending)
 * - Timeout on each query (default 30s) to prevent indefinite blocking
 * - Stats logging for monitoring queue depth and latency
 *
 * Standard: Adaptive Concurrency Control (Standard 024-005), v5.2.0+ serialization layer
 */

interface QueuedQuery {
  resolve: (value: any) => void;
  reject: (reason: Error) => void;
  query: string;
  params: any[] | undefined;
  timestamp: number;
}

export class DbConnectionSerializer {
  private queue: QueuedQuery[] = [];
  private isProcessing: boolean = false;
  private maxPending: number = 50;
  private defaultTimeoutMs: number = 30_000;

  // Stats tracking (reset on each GC cycle)
  private stats = {
    totalExecuted: 0,
    totalQueued: 0,
    totalTimedOut: 0,
    totalRejected: 0,
    avgWaitMs: 0,
    maxQueueDepth: 0,
    _waitSum: 0,
  };

  /**
   * Execute a database query through the serialization queue.
   * All calls are serialized — only one runs at a time.
   */
  async execute(
    dbInstance: any,
    query: string,
    params?: any[],
    timeoutMs?: number,
  ): Promise<any> {
    const waitStart = Date.now();

    // Check queue depth before queuing
    if (this.queue.length >= this.maxPending) {
      this.stats.totalRejected++;
      throw new Error(
        `[DbSerializer] Queue full (${this.queue.length}/${this.maxPending} pending). ` +
        `Database is overloaded. Try again later.`,
      );
    }

    return new Promise((resolve, reject) => {
      const entry: QueuedQuery = {
        resolve,
        reject,
        query,
        params,
        timestamp: waitStart,
      };

      this.queue.push(entry);
      this.stats.totalQueued++;

      // Track max queue depth
      if (this.queue.length > this.stats.maxQueueDepth) {
        this.stats.maxQueueDepth = this.queue.length;
      }

      // Start processing if not already running
      if (!this.isProcessing) {
        this.processQueue(dbInstance);
      }
    });
  }

  /**
   * Process the queue: execute queries one at a time.
   */
  private async processQueue(dbInstance: any): Promise<void> {
    this.isProcessing = true;

    while (this.queue.length > 0) {
      const entry = this.queue.shift()!;
      const waitMs = Date.now() - entry.timestamp;

      try {
        // Apply timeout to prevent indefinite blocking
        const timeoutPromise = new Promise<never>((_, reject) => {
          setTimeout(() => {
            this.stats.totalTimedOut++;
            reject(new Error(
              `[DbSerializer] Query timed out after ${this.defaultTimeoutMs}ms: ` +
              `${entry.query.substring(0, 60)}...`,
            ));
          }, this.defaultTimeoutMs);
        });

        const result = await Promise.race([
          dbInstance.query(entry.query, entry.params || []),
          timeoutPromise,
        ]);

        // Update stats
        this.stats.totalExecuted++;
        this.stats._waitSum += waitMs;
        if (this.stats.totalExecuted > 0) {
          this.stats.avgWaitMs = Math.round(this.stats._waitSum / this.stats.totalExecuted);
        }

        entry.resolve(result);
      } catch (error: any) {
        // Don't log transaction control statements as errors
        const trimmedQuery = entry.query.trim();
        if (!trimmedQuery.match(/^(BEGIN|COMMIT|ROLLBACK)/i)) {
          console.error(
            `[DbSerializer] Query failed after ${waitMs}ms wait: ` +
            `${error.message}`,
          );
        }
        this.stats.totalRejected++;
        entry.reject(error);
      }
    }

    this.isProcessing = false;
  }

  /**
   * Get current serializer stats for monitoring.
   */
  getStats(): {
    pending: number;
    isProcessing: boolean;
    totalExecuted: number;
    avgWaitMs: number;
    maxQueueDepth: number;
    totalTimedOut: number;
    totalRejected: number;
  } {
    return {
      pending: this.queue.length,
      isProcessing: this.isProcessing,
      ...this.stats,
    };
  }

  /**
   * Reset stats (call after GC or periodic health check).
   */
  resetStats(): void {
    this.stats = {
      totalExecuted: 0,
      totalQueued: 0,
      totalTimedOut: 0,
      totalRejected: 0,
      avgWaitMs: 0,
      maxQueueDepth: 0,
      _waitSum: 0,
    };
  }

  /**
   * Get a human-readable status string for logging.
   */
  getStatusString(): string {
    const s = this.getStats();
    return `[DbSerializer] pending=${s.pending} processed=${s.totalExecuted} ` +
      `avg_wait=${s.avgWaitMs}ms max_depth=${s.maxQueueDepth} ` +
      `timeout=${s.totalTimedOut} rejected=${s.totalRejected}`;
  }
}

// Export singleton instance — shared across all Database instances
export const dbSerializer = new DbConnectionSerializer();
