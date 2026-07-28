# Standard 005: Adaptive Concurrency Control

**Status:** ✅ ACTIVE | **Version:** 1.0 | **Date:** 2026-03-10
**Introduced:** v4.5.5 | **Component:** Engine / Utils
**Target:** All platforms (Android/Termux, Linux, macOS, Windows)

---

## 1. Executive Summary

Define an adaptive concurrency system that automatically adjusts processing modes based on available system memory. Prevents Out-Of-Memory (OOM) crashes on low-memory devices while maintaining high performance on high-memory systems.

**Problem Solved:** Parallel `Promise.all()` operations in search and context inflation cause memory exhaustion on devices with < 4GB RAM, leading to abrupt process termination (OOM kills).

**Solution:** Automatically detect available memory and switch between:
- **Sequential processing** (batch=1) for < 2GB free RAM
- **Adaptive processing** (batch=5) for 2-8GB free RAM
- **Parallel processing** (batch=20, CPU count) for > 8GB free RAM

### ⚠️ Limitations

**Sequential mode prevents OOM from parallel processing, but cannot fix large file issues.**

**Tested Results:**
| File Structure | Size | Molecules | Result |
|----------------|------|-----------|--------|
| 143 individual files | ~1MB each | ~1,000-2,000 each | ✅ Works perfectly |
| Single combined file | 98MB | 196,426 | ❌ Crash during inflation |

**Lesson:** Adaptive concurrency helps with parallel processing overhead, but file size/molecule density must also be controlled. Keep files <10MB with <10,000 molecules each.

---

## 2. Architecture

### 2.1 Memory Thresholds

| Mode | Free Memory Threshold | Batch Size | Use Case |
|------|----------------------|------------|----------|
| **Sequential** | < 2GB | 1 | Mobile, embedded, low-memory VMs |
| **Adaptive** | 2-8GB | 5 | Laptops, small servers |
| **Parallel** | > 8GB | 20 or CPU count | Workstations, high-memory servers |

### 2.2 Configuration Priority Chain

Configuration is resolved in this priority order (highest to lowest):

1. **Function parameters** - Direct call to `processWithAdaptiveConcurrency(items, processor, { batchSize: 10 })`
2. **user_settings.json** - `"adaptive_concurrency": { "environment": "low_memory" }`
3. **Environment variables** - `ANCHOR_CONCURRENCY_ENV=low_memory`
4. **Auto-detection** - System memory analysis
5. **Defaults** - Sequential mode as safe fallback

### 2.3 Configuration Schema

```typescript
interface AdaptiveConcurrencyConfig {
  // Environment mode override
  environment?: 'auto' | 'low_memory' | 'high_memory';
  
  // Memory thresholds (MB)
  sequential_threshold_mb?: number;  // Default: 2048
  parallel_threshold_mb?: number;    // Default: 8192
  
  // Concurrency limits
  max_concurrency?: number;          // Default: 5
  low_memory_batch_size?: number;    // Default: 1
  high_memory_batch_size?: number;   // Default: 20
}
```

**user_settings.json location:**
```json
{
  "adaptive_concurrency": {
    "environment": "auto",
    "sequential_threshold_mb": 2048,
    "parallel_threshold_mb": 8192,
    "max_concurrency": 5,
    "low_memory_batch_size": 1,
    "high_memory_batch_size": 20
  }
}
```

---

## 3. Implementation

### 3.1 Core Module: `adaptive-concurrency.ts`

```typescript
// engine/src/utils/adaptive-concurrency.ts

export interface SystemMemoryInfo {
  total: number;      // Total system memory in bytes
  free: number;       // Free memory in bytes
  used: number;       // Used memory in bytes
}

export interface ConcurrencyConfig {
  mode: 'sequential' | 'adaptive' | 'parallel';
  batchSize: number;
  freeMemoryMB: number;
}

/**
 * Get current system memory information
 */
export function getSystemMemoryInfo(): SystemMemoryInfo {
  const total = os.totalmem();
  const free = os.freemem();
  return { total, free, used: total - free };
}

/**
 * Determine if system should use sequential processing
 */
export function shouldUseSequential(): boolean {
  const config = getConfig().ADAPTIVE_CONCURRENCY;
  
  // Check environment override
  if (config.environment === 'low_memory') return true;
  if (config.environment === 'high_memory') return false;
  
  // Auto-detect based on free memory
  const { free } = getSystemMemoryInfo();
  const freeMB = Math.floor(free / 1024 / 1024);
  return freeMB < config.sequential_threshold_mb;
}

/**
 * Process items with adaptive concurrency
 */
export async function processWithAdaptiveConcurrency<T, R>(
  items: T[],
  processor: (item: T) => Promise<R>,
  options?: {
    batchSize?: number;
    forceSequential?: boolean;
    gcBetweenBatches?: boolean;
  }
): Promise<R[]> {
  const results: R[] = [];
  
  // Determine batch size
  let batchSize = options?.batchSize;
  if (!batchSize) {
    batchSize = shouldUseSequential() 
      ? getConfig().ADAPTIVE_CONCURRENCY.low_memory_batch_size
      : getConfig().ADAPTIVE_CONCURRENCY.high_memory_batch_size;
  }
  
  // Force sequential if requested
  if (options?.forceSequential) {
    batchSize = 1;
  }
  
  // Process in batches
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    
    if (batchSize === 1) {
      // Sequential processing
      for (const item of batch) {
        results.push(await processor(item));
      }
    } else {
      // Parallel processing within batch
      const batchResults = await Promise.all(
        batch.map(item => processor(item))
      );
      results.push(...batchResults);
    }
    
    // Optional GC hint between batches
    if (options?.gcBetweenBatches && global.gc) {
      global.gc();
    }
  }
  
  return results;
}
```

### 3.2 Integration Points

#### Context Inflator (`context-inflator.ts`)

```typescript
// BEFORE (OOM-prone):
const inflationPromises = atomPositions.map(pos =>
  this.inflateAtomPosition(pos, radius, maxResults)
);
const results = await Promise.all(inflationPromises);

// AFTER (Memory-safe):
const results = await processWithAdaptiveConcurrency(
  atomPositions,
  (pos) => this.inflateAtomPosition(pos, radius, maxResults),
  { gcBetweenBatches: shouldUseSequential() }
);
```

#### Search Service (`search.ts`)

```typescript
// BEFORE (OOM-prone):
const inflatedTerms = await Promise.all(
  searchTerms.map(term => inflateTerm(term))
);

// AFTER (Memory-safe):
const inflatedTerms = await processWithAdaptiveConcurrency(
  searchTerms,
  (term) => inflateTerm(term),
  { gcBetweenBatches: shouldUseSequential() }
);
```

---

## 4. Configuration

### 4.1 Environment Variables

| Variable | Values | Description |
|----------|--------|-------------|
| `ANCHOR_CONCURRENCY_ENV` | `auto`, `low_memory`, `high_memory` | Force specific mode |

### 4.2 User Settings

Location: `user_settings.json` (project root)

```json
{
  "adaptive_concurrency": {
    "environment": "auto",
    "sequential_threshold_mb": 2048,
    "parallel_threshold_mb": 8192,
    "max_concurrency": 5,
    "low_memory_batch_size": 1,
    "high_memory_batch_size": 20
  }
}
```

### 4.3 UI Toggle

A three-button selector in the UI allows users to override the automatic mode:

- **Low** - Force sequential processing (batch=1)
- **Auto** - Automatic detection based on free memory
- **High** - Force parallel processing (batch=20)

**Location:** Mobile drawer and desktop sidebar

---

## 5. Logging

The system logs concurrency decisions for debugging:

```
[AdaptiveConcurrency] Mode: SEQUENTIAL, Batch: 1, FreeMem: 2811MB
[AdaptiveConcurrency] Mode: PARALLEL, Batch: 20, FreeMem: 15234MB
```

---

## 6. Testing

### 6.1 Memory Stress Test

```typescript
// Test with varying memory conditions
const testQueries = [
  { name: "Simple", query: "test" },
  { name: "Complex", query: "search memory database query optimization" },
  { name: "Max Recall", query: "Rob and coda music education graph nodes" }
];

for (const test of testQueries) {
  const startMem = getSystemMemoryInfo();
  const result = await search(test.query);
  const endMem = getSystemMemoryInfo();
  
  console.log(`${test.name}: ${result.duration}ms, Memory delta: ${endMem.used - startMem.used}MB`);
}
```

### 6.2 Mode Verification

```bash
# Force low memory mode
ANCHOR_CONCURRENCY_ENV=low_memory pnpm start

# Check logs for sequential mode
grep "AdaptiveConcurrency" engine-startup.log
# Expected: [AdaptiveConcurrency] Mode: SEQUENTIAL, Batch: 1, ...
```

---

## 7. Performance Characteristics

### 7.1 Sequential Mode (< 2GB free)

- **Memory usage:** Low, bounded
- **Speed:** 2-3× slower than parallel
- **Stability:** No OOM crashes
- **Best for:** Mobile, embedded, resource-constrained environments

### 7.2 Adaptive Mode (2-8GB free)

- **Memory usage:** Moderate, controlled
- **Speed:** Balanced
- **Stability:** Stable under normal load
- **Best for:** Laptops, small servers

### 7.3 Parallel Mode (> 8GB free)

- **Memory usage:** Higher but manageable
- **Speed:** Fastest
- **Stability:** Stable with sufficient RAM
- **Best for:** Workstations, high-memory servers

---

## 8. Migration Guide

### For Existing Code

Replace `Promise.all()` with `processWithAdaptiveConcurrency()`:

```typescript
// BEFORE:
const results = await Promise.all(items.map(processItem));

// AFTER:
const results = await processWithAdaptiveConcurrency(
  items,
  processItem,
  { gcBetweenBatches: shouldUseSequential() }
);
```

### For New Code

Always use the adaptive concurrency utility for batch operations:

```typescript
import { processWithAdaptiveConcurrency } from '../utils/adaptive-concurrency.js';

async function processBatch(items: Item[]) {
  return processWithAdaptiveConcurrency(
    items,
    async (item) => {
      // Process single item
      return await transform(item);
    }
  );
}
```

---

## 9. Related Standards

- **Standard 006:** Mobile Search Optimization (complementary, focuses on search-specific optimizations)
- **Standard 007:** PGlite Memory Optimization (database-level memory management)
- **Standard 088:** Server Startup Sequence (initialization patterns)

---

## 10. References

- [Node.js os module](https://nodejs.org/api/os.html)
- [V8 Garbage Collection](https://v8.dev/blog/trash-talk)
- [Promise.all() concurrency patterns](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/all)

---

**Introduced:** v4.5.5
**Owner:** Anchor Engine Performance Team
**Last Updated:** 2026-03-10
