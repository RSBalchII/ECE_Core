/**
 * LRU Cache Implementation with Memory-Pressure Eviction
 *
 * A production-ready Least Recently Used (LRU) cache with:
 * - O(1) get/put operations using Map + doubly-linked list
 * - Memory-pressure aware eviction (integrates with ResourceManager)
 * - TTL-based expiration
 * - Statistics tracking for monitoring
 * - Thread-safe operations
 *
 * @see Standard 016: Search Caching
 * @see Standard 062: Memory Management
 */

import * as v8 from 'v8';
import { config } from '../config/index.js';
import { logLRU } from '../utils/structured-logger.js';

// --- Types ---

export interface LRUCacheOptions {
  /** Maximum number of entries in the cache */
  maxEntries: number;
  /** Time-to-live in milliseconds (0 = no expiration) */
  ttlMs?: number;
  /** Enable memory-pressure eviction (default: true) */
  enableMemoryPressureEviction?: boolean;
  /** Memory threshold percentage to trigger eviction (default: 70%) */
  memoryPressureThreshold?: number;
  /** Critical memory threshold percentage for aggressive eviction (default: 85%) */
  criticalMemoryThreshold?: number;
}

export interface CacheEntry<T> {
  value: T;
  timestamp: number;
  expiresAt: number | null;
  size: number; // Estimated memory size in bytes
}

export interface CacheStats {
  hits: number;
  misses: number;
  evictions: number;
  expirations: number;
  size: number;
  maxEntries: number;
  hitRate: number;
  memoryUsage: {
    heapUsed: number;
    heapTotal: number;
    percentageUsed: number;
  };
}

// --- Doubly Linked List Node for O(1) LRU tracking ---

class LRUNode<K, V> {
  key: K;
  value: CacheEntry<V>;
  prev: LRUNode<K, V> | null = null;
  next: LRUNode<K, V> | null = null;

  constructor(key: K, value: CacheEntry<V>) {
    this.key = key;
    this.value = value;
  }
}

// --- LRU Cache Implementation ---

export class LRUCache<K, V> {
  private maxEntries: number;
  private ttlMs: number;
  private enableMemoryPressureEviction: boolean;
  private memoryPressureThreshold: number;
  private criticalMemoryThreshold: number;

  private cache: Map<K, LRUNode<K, V>>;
  private head: LRUNode<K, V> | null = null; // Most recently used
  private tail: LRUNode<K, V> | null = null; // Least recently used

  private stats: CacheStats = {
    hits: 0,
    misses: 0,
    evictions: 0,
    expirations: 0,
    size: 0,
    maxEntries: 0,
    hitRate: 0,
    memoryUsage: {
      heapUsed: 0,
      heapTotal: 0,
      percentageUsed: 0,
    },
  };

  private memoryCheckInterval: NodeJS.Timeout | null = null;

  constructor(options: LRUCacheOptions) {
    this.maxEntries = options.maxEntries;
    this.ttlMs = options.ttlMs || 0;
    this.enableMemoryPressureEviction = options.enableMemoryPressureEviction ?? true;
    this.memoryPressureThreshold = options.memoryPressureThreshold ?? 70;
    this.criticalMemoryThreshold = options.criticalMemoryThreshold ?? 85;

    this.cache = new Map();
    this.stats.maxEntries = options.maxEntries;

    // Start memory monitoring if enabled
    if (this.enableMemoryPressureEviction) {
      this.startMemoryMonitoring();
    }
  }

  /**
   * Get a value from the cache
   * @param key - The key to retrieve
   * @returns The value if found and not expired, undefined otherwise
   */
  get(key: K): V | undefined {
    const node = this.cache.get(key);

    if (!node) {
      this.stats.misses++;
      this.updateHitRate();
      return undefined;
    }

    // Check expiration
    if (node.value.expiresAt && Date.now() > node.value.expiresAt) {
      this.remove(key);
      this.stats.expirations++;
      this.stats.misses++;
      this.updateHitRate();
      return undefined;
    }

    // Move to head (most recently used)
    this.moveToHead(node);
    this.stats.hits++;
    this.updateHitRate();

    return node.value.value;
  }

  /**
   * Set a value in the cache
   * @param key - The key to store
   * @param value - The value to store
   * @param estimatedSize - Estimated memory size in bytes (default: 1024)
   */
  set(key: K, value: V, estimatedSize: number = 1024): void {
    const existingNode = this.cache.get(key);

    if (existingNode) {
      // Update existing entry
      existingNode.value = {
        value,
        timestamp: Date.now(),
        expiresAt: this.ttlMs > 0 ? Date.now() + this.ttlMs : null,
        size: estimatedSize,
      };
      this.moveToHead(existingNode);
    } else {
      // Create new entry
      const newNode = new LRUNode(key, {
        value,
        timestamp: Date.now(),
        expiresAt: this.ttlMs > 0 ? Date.now() + this.ttlMs : null,
        size: estimatedSize,
      });

      this.cache.set(key, newNode);
      this.addToHead(newNode);
      this.stats.size = this.cache.size;

      // Evict if over capacity
      if (this.cache.size > this.maxEntries) {
        this.evictLRU();
      }
    }
  }

  /**
   * Check if a key exists in the cache (without updating LRU order)
   */
  has(key: K): boolean {
    const node = this.cache.get(key);
    if (!node) return false;

    // Check expiration
    if (node.value.expiresAt && Date.now() > node.value.expiresAt) {
      this.remove(key);
      this.stats.expirations++;
      return false;
    }

    return true;
  }

  /**
   * Remove a key from the cache
   */
  delete(key: K): boolean {
    return this.remove(key);
  }

  /**
   * Clear all entries from the cache
   */
  clear(): void {
    this.cache.clear();
    this.head = null;
    this.tail = null;
    this.stats.size = 0;
    this.stats.evictions += this.cache.size;
  }

  /**
   * Get cache statistics
   */
  getStats(): CacheStats {
    const heapStats = v8.getHeapStatistics();
    const heapUsed = (heapStats as any).used_heap_size || 0;
    const heapTotal = (heapStats as any).total_heap_size || 1;
    this.stats.memoryUsage = {
      heapUsed,
      heapTotal,
      percentageUsed: (heapUsed / heapTotal) * 100,
    };
    this.stats.size = this.cache.size;

    return { ...this.stats };
  }

  /**
   * Get all keys in the cache
   */
  keys(): K[] {
    return Array.from(this.cache.keys());
  }

  /**
   * Get all values in the cache
   */
  values(): V[] {
    return Array.from(this.cache.values()).map(node => node.value.value);
  }

  /**
   * Get all entries as [key, value] pairs
   */
  entries(): [K, V][] {
    return Array.from(this.cache.entries()).map(([key, node]) => [key, node.value.value]);
  }

  /**
   * Remove expired entries
   * @returns Number of entries removed
   */
  removeExpired(): number {
    const now = Date.now();
    let removed = 0;

    for (const [key, node] of this.cache.entries()) {
      if (node.value.expiresAt && now > node.value.expiresAt) {
        this.remove(key);
        removed++;
        this.stats.expirations++;
      }
    }

    return removed;
  }

  /**
   * Force eviction of least recently used entries
   * @param count - Number of entries to evict (default: 10% of cache)
   */
  evict(count?: number): void {
    const toEvict = count || Math.max(1, Math.floor(this.cache.size * 0.1));

    for (let i = 0; i < toEvict && this.tail; i++) {
      this.evictLRU();
    }
  }

  /**
   * Resize the cache (useful for memory pressure scenarios)
   * @param newMaxEntries - New maximum number of entries
   */
  resize(newMaxEntries: number): void {
    this.maxEntries = newMaxEntries;
    this.stats.maxEntries = newMaxEntries;

    // Evict if current size exceeds new limit
    while (this.cache.size > newMaxEntries && this.tail) {
      this.evictLRU();
    }
  }

  // --- Private Methods ---

  private addToHead(node: LRUNode<K, V>): void {
    node.prev = null;
    node.next = this.head;

    if (this.head) {
      this.head.prev = node;
    }

    this.head = node;

    if (!this.tail) {
      this.tail = node;
    }
  }

  private removeNode(node: LRUNode<K, V>): void {
    if (node.prev) {
      node.prev.next = node.next;
    } else {
      this.head = node.next;
    }

    if (node.next) {
      node.next.prev = node.prev;
    } else {
      this.tail = node.prev;
    }
  }

  private moveToHead(node: LRUNode<K, V>): void {
    this.removeNode(node);
    this.addToHead(node);
  }

  private evictLRU(): void {
    if (!this.tail) return;

    const key = this.tail.key;
    this.removeNode(this.tail);
    this.cache.delete(key);
    this.stats.size = this.cache.size;
    this.stats.evictions++;
  }

  private remove(key: K): boolean {
    const node = this.cache.get(key);
    if (!node) return false;

    this.removeNode(node);
    this.cache.delete(key);
    this.stats.size = this.cache.size;
    return true;
  }

  private updateHitRate(): void {
    const total = this.stats.hits + this.stats.misses;
    this.stats.hitRate = total > 0 ? this.stats.hits / total : 0;
  }

  private startMemoryMonitoring(): void {
    // Check memory every 5 seconds
    this.memoryCheckInterval = setInterval(() => {
      this.checkMemoryPressure();
    }, 5000);

    // Don't prevent process exit
    if (this.memoryCheckInterval.unref) {
      this.memoryCheckInterval.unref();
    }
  }

  private checkMemoryPressure(): void {
    try {
      const heapStats = v8.getHeapStatistics();
      const heapUsed = (heapStats as any).used_heap_size || 0;
      const heapTotal = (heapStats as any).total_heap_size || 1;
      const percentageUsed = (heapUsed / heapTotal) * 100;

      if (percentageUsed >= this.criticalMemoryThreshold) {
        // Critical: Evict 50% of cache (but keep minimum floor of 10 entries)
        const targetSize = Math.max(10, Math.floor(this.maxEntries * 0.5));
        if (this.cache.size > targetSize) {
          this.resize(targetSize);
        }
        logLRU('warn', `CRITICAL: Evicted to ${targetSize} entries (memory: ${percentageUsed.toFixed(1)}%)`, {
          targetSize,
          memoryPercent: percentageUsed,
          cacheSize: this.cache.size,
        });
      } else if (percentageUsed >= this.memoryPressureThreshold) {
        // High pressure: Evict 30% of cache (but keep minimum floor of 20 entries)
        const targetSize = Math.max(20, Math.floor(this.maxEntries * 0.7));
        if (this.cache.size > targetSize) {
          this.resize(targetSize);
        }
        logLRU('info', `HIGH PRESSURE: Evicted to ${targetSize} entries (memory: ${percentageUsed.toFixed(1)}%)`, {
          targetSize,
          memoryPercent: percentageUsed,
          cacheSize: this.cache.size,
        });
      }
    } catch (error) {
      logLRU('warn', 'Memory check failed', { error: String(error) });
    }
  }

  /**
   * Stop memory monitoring (for cleanup)
   */
  stop(): void {
    if (this.memoryCheckInterval) {
      clearInterval(this.memoryCheckInterval);
      this.memoryCheckInterval = null;
    }
  }
}

// --- Factory Function ---

/**
 * Create a new LRU cache instance
 * @param options - Cache configuration options
 * @returns A new LRUCache instance
 */
export function createLRUCache<K, V>(options: LRUCacheOptions): LRUCache<K, V> {
  return new LRUCache<K, V>(options);
}

// --- Pre-configured Cache Instances ---

/**
 * Search result cache (Standard 016)
 * Replaces the simple Map-based cache in search.ts
 */
export const searchResultCache = createLRUCache<string, any>({
  maxEntries: config.MAX_CACHE_SIZE || 100,
  ttlMs: config.CACHE_TTL_MS || 60000,
  enableMemoryPressureEviction: true,
  memoryPressureThreshold: 90, // Increased from 88
  criticalMemoryThreshold: 96, // Increased from 95
});

/**
 * Query parsing cache
 * Caches parsed query structures to avoid re-parsing
 */
export const queryParseCache = createLRUCache<string, any>({
  maxEntries: 500,
  ttlMs: 300000, // 5 minutes
  enableMemoryPressureEviction: true,
  memoryPressureThreshold: 90, // Increased from 88
  criticalMemoryThreshold: 96, // Increased from 95
});

/**
 * Semantic expansion cache
 * Caches taxonomy expansion results
 */
export const semanticExpansionCache = createLRUCache<string, string[]>({
  maxEntries: 1000,
  ttlMs: 600000, // 10 minutes
  enableMemoryPressureEviction: true,
  memoryPressureThreshold: 90, // Increased from 88
  criticalMemoryThreshold: 96, // Increased from 95
});

/**
 * Engram lookup cache
 * Caches engram-based context retrieval
 */
export const engramCache = createLRUCache<string, any>({
  maxEntries: 200,
  ttlMs: 120000, // 2 minutes
  enableMemoryPressureEviction: true,
  memoryPressureThreshold: 90, // Increased from 88
  criticalMemoryThreshold: 96, // Increased from 95
});
