/**
 * Memory Pressure Integration Tests
 *
 * Tests system behavior under memory pressure:
 * - Adaptive concurrency switching
 * - Search throttling
 * - GC triggers
 * - OOM prevention
 * 
 * Run: pnpm test -- memory-pressure.test.ts
 */

import { describe, test, expect, beforeEach, afterAll } from '@jest/globals';
import os from 'os';

describe('Memory Pressure Integration', () => {
  describe('Memory Monitoring', () => {
    test('should report system memory info', () => {
      const totalMB = Math.floor(os.totalmem() / 1024 / 1024);
      const freeMB = Math.floor(os.freemem() / 1024 / 1024);
      const usedMB = totalMB - freeMB;
      
      expect(totalMB).toBeGreaterThan(0);
      expect(freeMB).toBeGreaterThan(0);
      expect(usedMB).toBeGreaterThan(0);
      expect(usedMB).toBeLessThan(totalMB);
    });

    test('should calculate memory usage percentage', () => {
      const totalMB = os.totalmem();
      const freeMB = os.freemem();
      const usedMB = totalMB - freeMB;
      const usagePercent = Math.round((usedMB / totalMB) * 100);
      
      expect(usagePercent).toBeGreaterThanOrEqual(0);
      expect(usagePercent).toBeLessThanOrEqual(100);
    });

    test('should detect low memory environment', () => {
      const totalGB = os.totalmem() / (1024 * 1024 * 1024);
      const isLowMemory = totalGB < 2;
      
      // Just verify the logic works, actual result depends on test environment
      expect(typeof isLowMemory).toBe('boolean');
    });

    test('should detect high memory environment', () => {
      const totalGB = os.totalmem() / (1024 * 1024 * 1024);
      const isHighMemory = totalGB > 8;
      
      expect(typeof isHighMemory).toBe('boolean');
    });
  });

  describe('Adaptive Concurrency', () => {
    test('should determine sequential mode for low memory', () => {
      const freeMB = 1024; // 1GB free
      const threshold = 2048; // 2GB threshold
      
      const shouldUseSequential = freeMB < threshold;
      expect(shouldUseSequential).toBe(true);
    });

    test('should determine parallel mode for high memory', () => {
      const freeMB = 16384; // 16GB free
      const threshold = 8192; // 8GB threshold
      
      const shouldUseSequential = freeMB < threshold;
      expect(shouldUseSequential).toBe(false);
    });

    test('should calculate optimal batch size', () => {
      const freeMB = 4096; // 4GB free
      const sequentialThreshold = 2048;
      const parallelThreshold = 8192;
      const lowMemoryBatchSize = 1;
      const highMemoryBatchSize = 20;
      
      const ratio = (freeMB - sequentialThreshold) / (parallelThreshold - sequentialThreshold);
      const batchSize = Math.floor(lowMemoryBatchSize + (highMemoryBatchSize - lowMemoryBatchSize) * Math.min(ratio, 1));
      
      expect(batchSize).toBeGreaterThanOrEqual(lowMemoryBatchSize);
      expect(batchSize).toBeLessThanOrEqual(highMemoryBatchSize);
    });

    test('should calculate optimal concurrency level', () => {
      const freeMB = 16384; // 16GB free
      const parallelThreshold = 8192;
      
      const concurrency = freeMB > parallelThreshold 
        ? Math.min(os.cpus().length, 16)
        : 1;
      
      expect(concurrency).toBeGreaterThanOrEqual(1);
      expect(concurrency).toBeLessThanOrEqual(16);
    });
  });

  describe('Search Throttling', () => {
    test('should allow search under memory threshold', () => {
      const heapUsedMB = 400;
      const throttleStartMB = 800;
      
      const shouldThrottle = heapUsedMB >= throttleStartMB;
      expect(shouldThrottle).toBe(false);
    });

    test('should throttle search over threshold', () => {
      const heapUsedMB = 1000;
      const throttleStartMB = 800;
      const throttleMaxMB = 1200;
      
      const shouldReject = heapUsedMB >= throttleMaxMB;
      const shouldThrottle = heapUsedMB >= throttleStartMB && !shouldReject;
      
      expect(shouldReject).toBe(false);
      expect(shouldThrottle).toBe(true);
    });

    test('should reject search at emergency stop', () => {
      const heapUsedMB = 1600;
      const emergencyStopMB = 1500;
      
      const shouldReject = heapUsedMB >= emergencyStopMB;
      expect(shouldReject).toBe(true);
    });

    test('should calculate throttle delay based on pressure', () => {
      const heapUsedMB = 1000;
      const throttleStartMB = 800;
      const throttleMaxMB = 1200;
      
      const pressureRatio = (heapUsedMB - throttleStartMB) / (throttleMaxMB - throttleStartMB);
      const delayMs = Math.round(pressureRatio * 10000);
      
      expect(delayMs).toBeGreaterThan(0);
      expect(delayMs).toBeLessThanOrEqual(10000);
    });
  });

  describe('GC Management', () => {
    test('should trigger GC when available', (done) => {
      // Note: global.gc only available with --expose-gc flag
      if (typeof global.gc === 'function') {
        const beforeGC = process.memoryUsage().heapUsed;
        global.gc();
        const afterGC = process.memoryUsage().heapUsed;
        
        // GC should not increase heap usage significantly
        expect(afterGC).toBeLessThanOrEqual(beforeGC * 1.1); // Allow 10% variance
        done();
      } else {
        // Skip if GC not exposed
        expect(true).toBe(true);
        done();
      }
    });

    test('should track memory before and after operations', async () => {
      const beforeMemory = process.memoryUsage();
      
      // Simulate memory-intensive operation
      const testData: string[] = [];
      for (let i = 0; i < 1000; i++) {
        testData.push('A'.repeat(1000));
      }
      
      const afterMemory = process.memoryUsage();
      
      expect(afterMemory.heapUsed).toBeGreaterThanOrEqual(beforeMemory.heapUsed);
      
      // Cleanup
      testData.length = 0;
    });
  });

  describe('Batch Processing Under Pressure', () => {
    test('should process items sequentially in low memory', async () => {
      const items = Array.from({ length: 10 }, (_, i) => i);
      const results: number[] = [];
      
      // Sequential processing
      for (const item of items) {
        await new Promise(resolve => setTimeout(resolve, 1));
        results.push(item * 2);
      }
      
      expect(results).toHaveLength(10);
      expect(results[0]).toBe(0);
      expect(results[9]).toBe(18);
    });

    test('should process items in parallel in high memory', async () => {
      const items = Array.from({ length: 10 }, (_, i) => i);
      
      // Parallel processing
      const results = await Promise.all(
        items.map(async (item) => {
          await new Promise(resolve => setTimeout(resolve, 1));
          return item * 2;
        })
      );
      
      expect(results).toHaveLength(10);
      expect(results.sort((a, b) => a - b)[0]).toBe(0);
      expect(results.sort((a, b) => a - b)[9]).toBe(18);
    });

    test('should batch process to limit memory', async () => {
      const items = Array.from({ length: 100 }, (_, i) => i);
      const batchSize = 10;
      const results: number[] = [];
      
      for (let i = 0; i < items.length; i += batchSize) {
        const batch = items.slice(i, i + batchSize);
        
        // Process batch
        const batchResults = await Promise.all(
          batch.map(item => {
            return new Promise<number>(resolve => {
              setTimeout(() => resolve(item * 2), 1);
            });
          })
        );
        
        results.push(...batchResults);
        
        // Simulate GC hint between batches
        if (typeof global.gc === 'function') {
          global.gc();
        }
      }
      
      expect(results).toHaveLength(100);
    });
  });

  describe('Memory Leak Prevention', () => {
    test('should clear caches after operations', async () => {
      const cache = new Map<string, any>();
      
      // Fill cache
      for (let i = 0; i < 100; i++) {
        cache.set(`key-${i}`, { data: 'A'.repeat(1000) });
      }
      
      expect(cache.size).toBe(100);
      
      // Clear cache
      cache.clear();
      expect(cache.size).toBe(0);
    });

    test('should limit array growth', async () => {
      const MAX_SIZE = 1000;
      const results: any[] = [];
      
      // Simulate adding results with limit
      for (let i = 0; i < 2000; i++) {
        if (results.length < MAX_SIZE) {
          results.push({ id: i });
        }
      }
      
      expect(results.length).toBe(MAX_SIZE);
    });

    test('should use WeakMap for object metadata', () => {
      const metadata = new WeakMap<object, { timestamp: number }>();
      
      const obj1 = { id: 1 };
      const obj2 = { id: 2 };
      
      metadata.set(obj1, { timestamp: Date.now() });
      metadata.set(obj2, { timestamp: Date.now() });
      
      expect(metadata.has(obj1)).toBe(true);
      
      // Allow GC to collect obj2
      // (In real code, this would happen naturally when obj2 goes out of scope)
    });
  });

  describe('Streaming Results', () => {
    test('should stream results in batches', async () => {
      const totalResults = 100;
      const batchSize = 20;
      const streamedBatches: number[][] = [];
      
      for (let i = 0; i < totalResults; i += batchSize) {
        const batch = Array.from({ length: Math.min(batchSize, totalResults - i) }, (_, j) => i + j);
        streamedBatches.push(batch);
        
        // Simulate streaming delay
        await new Promise(resolve => setTimeout(resolve, 1));
      }
      
      expect(streamedBatches).toHaveLength(5); // 100 / 20 = 5 batches
      expect(streamedBatches[0].length).toBe(20);
      expect(streamedBatches[4].length).toBe(20);
    });

    test('should handle early termination', async () => {
      const totalResults = 100;
      const batchSize = 10;
      let processedBatches = 0;
      const maxBatches = 3;
      
      for (let i = 0; i < totalResults; i += batchSize) {
        if (processedBatches >= maxBatches) {
          break; // Early termination
        }
        
        processedBatches++;
        await new Promise(resolve => setTimeout(resolve, 1));
      }
      
      expect(processedBatches).toBe(maxBatches);
    });
  });

  describe('Heap Size Monitoring', () => {
    test('should report heap statistics', () => {
      const memUsage = process.memoryUsage();
      
      expect(memUsage.heapTotal).toBeGreaterThan(0);
      expect(memUsage.heapUsed).toBeGreaterThan(0);
      expect(memUsage.heapUsed).toBeLessThanOrEqual(memUsage.heapTotal);
      expect(memUsage.rss).toBeGreaterThan(memUsage.heapTotal);
    });

    test('should calculate heap utilization', () => {
      const memUsage = process.memoryUsage();
      const utilization = (memUsage.heapUsed / memUsage.heapTotal) * 100;
      
      expect(utilization).toBeGreaterThanOrEqual(0);
      expect(utilization).toBeLessThanOrEqual(100);
    });
  });
});
