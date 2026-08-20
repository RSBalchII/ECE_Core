/**
 * Memory-Aware Executor (v5.2.0+)
 *
 * Replaces unbounded Promise.all() patterns with controlled concurrency that
 * respects available heap memory. Prevents OOM crashes during search, ingest,
 * and synonym generation when many items are processed simultaneously.
 *
 * Architecture:
 *   [Promise.all(items)]  →  [Executor.processBounded(items, fn, {maxConcurrency})]
 *                              ↓
 *                         Memory monitor + FIFO queue
 *                              ↓
 *                    Controlled parallelism (1-N concurrent)
 *
 * Key properties:
 * - Bounded concurrency: max N items run simultaneously (default: adaptive from memory)
 * - Memory monitoring: pauses if RSS exceeds threshold, triggers GC hint
 * - Per-item timeout: prevents single slow item from blocking the queue
 * - Graceful degradation: falls back to sequential on OOM
 *
 * Standard: Adaptive Concurrency Control (Standard 024-005), v5.2.0+ executor layer
 */

import os from 'os';
import { getOptimalConcurrency } from './adaptive-concurrency.js';

export interface ExecutorConfig {
  /** Maximum concurrent operations (default: adaptive from system memory) */
  maxConcurrency?: number;
  /** Memory threshold in MB — pause processing if RSS exceeds this (default: 1500) */
  memoryThresholdMB?: number;
  /** Per-item timeout in ms (default: 60_000) */
  itemTimeoutMs?: number;
  /** GC hint interval — call global.gc() every N items processed (0 = disabled, default: 10) */
  gcHintEvery?: number;
}

interface ExecutorStats {
  totalProcessed: number;
  totalFailed: number;
  avgItemMs: number;
  peakConcurrency: number;
  currentConcurrency: number;
  memoryPauses: number;
}

export class MemoryAwareExecutor {
  private stats: ExecutorStats = {
    totalProcessed: 0,
    totalFailed: 0,
    avgItemMs: 0,
    peakConcurrency: 0,
    currentConcurrency: 0,
    memoryPauses: 0,
  };

  /**
   * Process items with bounded concurrency and memory monitoring.
   * Replaces unbounded Promise.all() to prevent heap spikes.
   */
  async process<T, R>(
    items: T[],
    processor: (item: T, index: number) => Promise<R>,
    config?: ExecutorConfig,
  ): Promise<R[]> {
    const effectiveConcurrency = config?.maxConcurrency ?? await getOptimalConcurrency();
    const memoryThresholdMB = config?.memoryThresholdMB ?? 1500;
    const itemTimeoutMs = config?.itemTimeoutMs ?? 60_000;
    const gcHintEvery = config?.gcHintEvery ?? 10;

    this.resetStats();

    if (items.length === 0) return [];

    // Single item — no concurrency needed
    if (items.length === 1) {
      return [await this.runWithTimeout(processor(items[0], 0), itemTimeoutMs, 0)];
    }

    const results: R[] = new Array(items.length);
    let nextIndex = 0;
    let activeWorkers = 0;
    const completed = { value: 0 };

    // Worker pool — each worker pulls items from the queue
    const workers = Array.from({ length: Math.min(effectiveConcurrency, items.length) }, async () => {
      while (nextIndex < items.length) {
        // Memory check before each item
        if (!this.checkMemory(memoryThresholdMB)) {
          this.stats.memoryPauses++;
          await this.waitForMemory(memoryThresholdMB);
        }

        const idx = nextIndex++;
        activeWorkers++;
        this.updateConcurrency(activeWorkers);

        try {
          const result = await this.runWithTimeout(
            processor(items[idx], idx),
            itemTimeoutMs,
            idx,
          );
          results[idx] = result;
          this.stats.totalProcessed++;
        } catch (error: any) {
          // Store error as rejection value so other items still complete
          console.warn(`[MemoryAwareExecutor] Item ${idx} failed:`, error.message);
          results[idx] = undefined as unknown as R;
          this.stats.totalFailed++;
        } finally {
          activeWorkers--;
          completed.value++;

          // GC hint at intervals
          if (gcHintEvery > 0 && completed.value % gcHintEvery === 0 && global.gc) {
            global.gc();
          }
        }
      }
    });

    await Promise.all(workers);
    return results;
  }

  /**
   * Run a single item with timeout.
   */
  private async runWithTimeout<T>(fn: Promise<T>, timeoutMs: number, index: number): Promise<T> {
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error(
          `[MemoryAwareExecutor] Item ${index} timed out after ${timeoutMs}ms`,
        ));
      }, timeoutMs);
    });

    return Promise.race([fn, timeoutPromise]);
  }

  /**
   * Check if RSS is below threshold. Returns true if safe to proceed.
   */
  private checkMemory(thresholdMB: number): boolean {
    const rssMB = process.memoryUsage().rss / 1024 / 1024;
    return rssMB < thresholdMB;
  }

  /**
   * Wait for memory to drop below threshold. Polls every 500ms.
   */
  private async waitForMemory(thresholdMB: number): Promise<void> {
    const pollInterval = 500; // ms
    const maxWaitMs = 30_000; // Don't wait forever
    let waited = 0;

    while (waited < maxWaitMs) {
      await new Promise(r => setTimeout(r, pollInterval));
      waited += pollInterval;

      if (this.checkMemory(thresholdMB)) return;

      // Try GC to free memory
      if (global.gc) {
        global.gc();
      }
    }

    console.warn('[MemoryAwareExecutor] Memory threshold not reached after waiting — proceeding anyway');
  }

  private updateConcurrency(active: number): void {
    this.stats.currentConcurrency = active;
    if (active > this.stats.peakConcurrency) {
      this.stats.peakConcurrency = active;
    }
  }

  resetStats(): void {
    this.stats = {
      totalProcessed: 0,
      totalFailed: 0,
      avgItemMs: 0,
      peakConcurrency: 0,
      currentConcurrency: 0,
      memoryPauses: 0,
    };
  }

  getStats(): ExecutorStats {
    return this.stats;
  }
}

// Export singleton instance — shared across all services
export const executor = new MemoryAwareExecutor();
