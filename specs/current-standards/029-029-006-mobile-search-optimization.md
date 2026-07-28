# Standard 006: Mobile Search Optimization — Memory-Constrained Retrieval

**Status:** 🚧 DRAFT | **Version:** 1.0 | **Date:** 2026-03-09
**Introduced:** v4.5.5 | **Component:** Engine / Search Service
**Target:** Android/Termux, Raspberry Pi, embedded devices (< 2GB RAM)

---

## 1. Executive Summary

Define memory-constrained search strategies for Anchor Engine deployments on resource-limited devices. Prevents Out-Of-Memory (OOM) crashes while maintaining search quality through:

1. **Sequential processing** (not parallel)
2. **Bounded result windows** (not unbounded inflation)
3. **Streaming result handling** (not batch accumulation)
4. **Aggressive garbage collection** triggers

**Problem Solved:** Current semantic search uses parallel inflation with large radius windows, causing OOM on mobile devices when querying large corpora.

---

## 2. OOM Root Cause Analysis

### Current Implementation Issues

| Issue | Location | Impact |
|-------|----------|--------|
| **Parallel inflation** | `Promise.all(inflationPromises)` line ~385 | Spawns N concurrent disk reads + memory allocations |
| **Unbounded radius** | `radiusPerTerm = Math.min(32000, ...)` | Up to 32KB × 2 × N results in memory |
| **No content SELECT** | `SELECT a.id, a.source_path...` (no content) | Forces inflation for scoring |
| **Full accumulation** | `inflatedResults.push(...termResults)` | All results held before filtering |
| **No GC hints** | Missing `global.gc()` calls | Memory not freed between terms |

### Memory Math (Problem)

Query: "Rob and coda working on anchor"
- Terms after filtering: ["Rob", "coda", "anchor"] ("working" is stopword)
- Radius per term: ~16,000 chars (with typical budget)
- Results per term: ~10 windows
- Window size: ~32KB each
- **Peak memory**: 3 terms × 10 results × 32KB = **~960KB** (just for content)
- **With overhead**: ~5-10MB per query
- **Concurrent queries**: Stack overflow

On Termux with 1-2GB RAM and Node.js overhead, this causes OOM.

### ⚠️ Large File Warning

**CRITICAL:** Files >10MB with >10,000 molecules cause OOM even with sequential processing.

**Tested:**
- ✅ **143 individual files** (~1MB each): Search works perfectly
- ❌ **Single 98MB file** (196,426 molecules): Crash during context inflation

**Root Cause:** Context inflation loads byte ranges from source files. Large files with high molecule density create memory pressure that exceeds Android limits.

**Solution:** Keep files in natural directory structure. Do NOT combine into monolithic files.

---

## 3. Mobile Search Architecture

### 3.1. Sequential Inflation Strategy

```typescript
// BEFORE (OOM-prone):
const inflationPromises = termsToInflate.map(term =>
  ContextInflator.inflateFromAtomPositions(term, radius, maxResults, ...)
);
const results = await Promise.all(inflationPromises);

// AFTER (Memory-safe):
const results: SearchResult[] = [];
for (const term of termsToInflate) {
  const termResults = await ContextInflator.inflateFromAtomPositions(
    term, radius, maxResults, ...
  );
  results.push(...termResults);
  
  // Force GC after each term
  if (global.gc) global.gc();
}
```

**Trade-off:** 2-3× slower but memory-bound.

### 3.2. Bounded Radius

```typescript
// Mobile-specific limits
const MOBILE_MAX_RADIUS = 2000;      // 2KB max (vs 32KB desktop)
const MOBILE_MAX_RESULTS = 5;        // 5 results per term (vs 10+ desktop)
const MOBILE_BATCH_SIZE = 3;         // Process 3 terms before GC

function getMobileSearchConfig(maxChars: number, termCount: number) {
  const termBudget = Math.min(maxChars / termCount, 8000); // Cap at 8KB per term
  return {
    radius: Math.min(1000, Math.floor(termBudget / 4)),
    maxResultsPerTerm: MOBILE_MAX_RESULTS,
    sequential: true,
    forceGC: true
  };
}
```

### 3.3. Streaming Results

Don't accumulate all results before filtering:

```typescript
// BEFORE:
const allResults: SearchResult[] = [];
for (const term of terms) {
  const termResults = await inflate(term);
  allResults.push(...termResults); // Accumulates everything
}
allResults.sort(...); // Sort all
const filtered = applyBudget(allResults); // Then filter

// AFTER:
const budgetRemaining = maxChars;
const finalResults: SearchResult[] = [];

for (const term of terms) {
  const termResults = await inflate(term);
  
  // Sort and filter immediately
  termResults.sort((a, b) => score(b) - score(a));
  
  for (const result of termResults) {
    if (budgetRemaining <= 0) break;
    const content = result.content?.slice(0, budgetRemaining);
    finalResults.push({ ...result, content });
    budgetRemaining -= content.length;
  }
  
  if (global.gc) global.gc();
}
```

### 3.4. Two-Pass Scoring (Avoid Inflation for Scoring)

Current issue: `calculateSemanticScore` is called with empty content because the initial query doesn't SELECT content.

**Solution:** Two-pass approach:

```typescript
// PASS 1: Lightweight FTS query with content
const initialQuery = `
  SELECT a.id, a.content, a.source_path, ...
  FROM atoms a
  WHERE to_tsvector('simple', a.content) @@ to_tsquery('simple', $1)
  LIMIT 20  -- Hard limit for mobile
`;

// Score in-memory (small result set)
const scored = rows.map(row => ({
  ...row,
  score: calculateSemanticScore(row.content, queryEntities, terms, pairs)
}));

// PASS 2: Inflate ONLY top-N results
const topResults = scored
  .sort((a, b) => b.score - a.score)
  .slice(0, 10); // Only inflate top 10

const inflated = await ContextInflator.inflate(topResults, maxChars, radius);
```

**Benefit:** Inflation (expensive) only happens on high-quality candidates.

---

## 4. Implementation

### 4.1. Mobile Detection

```typescript
function isMobileEnvironment(): boolean {
  // Check for Android/Termux
  if (process.platform === 'android') return true;
  
  // Check available memory
  const os = require('os');
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  
  // Mobile if < 2GB total or < 500MB free
  return totalMem < 2 * 1024 * 1024 * 1024 || 
         freeMem < 500 * 1024 * 1024;
}
```

### 4.2. Search Mode Selection

```typescript
export async function executeSemanticSearch(
  query: string,
  buckets?: string[],
  maxChars: number = 5242,
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  explicitTags: string[] = [],
  codeWeight: number = 1.0
): Promise<SearchResult[]> {
  
  const isMobile = isMobileEnvironment();
  
  if (isMobile) {
    return executeMobileSearch(query, buckets, maxChars, provenance, explicitTags, codeWeight);
  } else {
    return executeDesktopSearch(query, buckets, maxChars, provenance, explicitTags, codeWeight);
  }
}
```

### 4.3. Mobile Search Implementation

```typescript
async function executeMobileSearch(
  query: string,
  buckets?: string[],
  maxChars: number = 3000,  // Lower default for mobile
  provenance = 'all',
  explicitTags: string[] = [],
  codeWeight = 1.0
): Promise<SearchResult[]> {
  
  const terms = extractSearchTerms(query);
  const config = getMobileSearchConfig(maxChars, terms.length);
  
  // PASS 1: FTS with content (limited rows)
  const candidates = await fetchCandidatesWithContent(query, {
    limit: 20,
    buckets,
    provenance
  });
  
  // Score candidates (have content already)
  const scored = candidates.map(c => ({
    ...c,
    score: calculateSemanticScore(c.content, query, terms)
  }));
  
  // Take top N only
  const topCandidates = scored
    .sort((a, b) => b.score - a.score)
    .slice(0, config.maxResultsPerTerm * terms.length);
  
  // PASS 2: Sequential inflation with bounded radius
  const results: SearchResult[] = [];
  let budgetRemaining = maxChars;
  
  for (let i = 0; i < topCandidates.length; i++) {
    const candidate = topCandidates[i];
    
    // Inflate single result
    const inflated = await ContextInflator.inflate(
      [candidate], 
      budgetRemaining,
      config.radius
    );
    
    if (inflated.length > 0 && inflated[0].content) {
      const content = inflated[0].content.slice(0, budgetRemaining);
      results.push({ ...inflated[0], content });
      budgetRemaining -= content.length;
    }
    
    // GC every N items
    if (i % 3 === 0 && global.gc) {
      global.gc();
    }
    
    if (budgetRemaining <= 0) break;
  }
  
  return results;
}
```

---

## 5. ContextInflator Optimizations

### 5.1. Single-Result Inflation

Add method for inflating one result at a time:

```typescript
static async inflateOne(
  result: SearchResult,
  radius: number
): Promise<SearchResult | null> {
  // Skip batch processing overhead
  // Direct file read with minimal allocations
  // Return immediately
}
```

### 5.2. Memory-Mapped File Reading

For large files, use streaming reads:

```typescript
// Instead of fs.readFile (loads entire file)
const fd = await fs.promises.open(filePath, 'r');
const buffer = Buffer.alloc(radius * 2);
await fd.read(buffer, 0, radius * 2, startByte - radius);
await fd.close();
```

### 5.3. String Pooling

Reuse string objects for common paths/sources:

```typescript
const sourcePool = new Map<string, string>();

function getPooledSource(source: string): string {
  if (!sourcePool.has(source)) {
    sourcePool.set(source, source);
  }
  return sourcePool.get(source)!;
}
```

---

## 6. Configuration

### 6.1. User Settings

Add to `user_settings.json`:

```json
{
  "search": {
    "mode": "auto",
    "mobile": {
      "max_radius": 2000,
      "max_results_per_term": 5,
      "sequential_inflation": true,
      "force_gc": true,
      "content_select": true
    },
    "desktop": {
      "max_radius": 32000,
      "max_results_per_term": 10,
      "sequential_inflation": false,
      "force_gc": false,
      "content_select": false
    }
  }
}
```

### 6.2. Environment Variables

```bash
# Force mobile mode
ANCHOR_MOBILE_MODE=1

# Custom memory threshold (bytes)
ANCHOR_MOBILE_MEMORY_THRESHOLD=500000000

# Disable GC hints (if causing performance issues)
ANCHOR_DISABLE_GC_HINTS=1
```

---

## 7. Performance Targets

| Metric | Desktop | Mobile (Current) | Mobile (Target) |
|--------|---------|------------------|-----------------|
| Query Time | 500ms | OOM / 10s+ | < 3s |
| Memory Peak | 200MB | 1GB+ (OOM) | < 150MB |
| Results Quality | High | N/A | Medium-High |
| Concurrent Queries | 5+ | 1 (crashes) | 2-3 |

---

## 8. Testing

### 8.1. Memory Profiling

```typescript
// Add to search code
const memBefore = process.memoryUsage();
const results = await executeSemanticSearch(query);
const memAfter = process.memoryUsage();

console.log(`[Memory] Heap used: ${(memAfter.heapUsed - memBefore.heapUsed) / 1024 / 1024}MB`);
```

### 8.2. Stress Test Query

```
"Rob and coda working on anchor"
```

This query:
- Has multiple terms
- Requires relationship detection
- Triggers large radius inflation
- Previously caused OOM

**Success Criteria:**
- Completes without OOM
- Returns results in < 5s
- Memory usage < 200MB

---

## 9. Migration Guide

### Phase 1: Immediate Fix (v4.5.5)

1. Add mobile detection
2. Implement sequential inflation
3. Add GC hints
4. Lower default radius on mobile

### Phase 2: Optimization (v4.5.6)

1. Two-pass scoring
2. Single-result inflation method
3. Streaming result handling

### Phase 3: Advanced (v4.6.0)

1. Memory-mapped file I/O
2. Result caching
3. Query planning based on corpus size

---

## 10. Related Standards

- **Standard 104:** Universal Semantic Search — base search algorithm
- **Standard 009:** Illuminate BFS — graph traversal
- **Standard 008:** Radial Distillation — corpus compression
- **Standard 007:** PGlite Memory Optimization — database layer

---

**Introduced:** v4.5.5
**Owner:** Anchor Engine Team
**Status:** DRAFT — Implementation Required
