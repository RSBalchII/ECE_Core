# Standard 014: Search Algorithm Testing Methodology

**Status:** Active  
**Version:** 1.0.0  
**Created:** 2026-05-18  
**Author:** RS Balch II  

---

## Overview

This standard defines the methodology for testing search algorithms in Anchor Engine, ensuring comprehensive coverage from most complex to simplest queries. The goal is to identify real gaps in search capabilities by systematically exercising each algorithm with progressively easier test cases.

---

## 1. Test Order: Hardest → Easiest

Tests should be ordered from **most challenging** to **simplest** queries. This approach:

1. **Stress-tests the system first** - If complex searches fail, simple ones may still work
2. **Reveals edge cases early** - Complex queries expose boundary conditions
3. **Provides clear regression baselines** - Simple tests serve as quick health checks
4. **Enables targeted debugging** - Failures in hard tests point to specific algorithmic issues

### Test Categories (Ordered)

| Priority | Category | Example Queries | Purpose |
|----------|----------|-----------------|---------|
| **P0** | Semantic/Complex | "authentication and authorization in Node.js best practices" | Multi-concept, requires understanding relationships |
| **P1** | Tag-based Advanced | `#test #api #node` with filters | Tests tag intersection logic |
| **P2** | Byte Offset Search | "function findAnchors" with offset tracking | Verifies content boundary handling |
| **P3** | FTS Basic | "workspace" or "atom" | Standard full-text search |
| **P4** | Empty/All Results | "" (empty query) | Returns all indexed content |

---

## 2. Test Structure

### 2.1 Test File Format

```typescript
// tests/unit/search-algorithms.test.ts
import { describe, it, expect } from 'vitest';
import { AnchorClient } from '../../packages/api-client/src/index';

describe('Search Algorithm Tests (Hardest → Easiest)', () => {
  const client = new AnchorClient({ baseUrl: 'http://localhost:3160' });

  // P0 - HARDEST: Semantic search with complex multi-concept queries
  it('P0 semantic-search-complex', async () => {
    const results = await client.search(
      'authentication and authorization in Node.js best practices',
      { 
        strategy: 'semantic',
        maxResults: 10 
      }
    );
    expect(results.totalResults).toBeGreaterThan(0);
    validateSearchResults(results);
    logResults('P0 semantic-search-complex', results);
  });

  // P1 - Hard: Tag-based search with multiple filters
  it('P1 tag-search-multi-filter', async () => {
    const results = await client.search('#test #api #node', { 
      mode: 'tags',
      maxResults: 10 
    });
    expect(results.totalResults).toBeGreaterThan(0);
    validateSearchResults(results);
    logResults('P1 tag-search-multi-filter', results);
  });

  // P2 - Medium-Hard: Byte offset search with content boundaries
  it('P2 byte-offset-content-boundary', async () => {
    const results = await client.search('function findAnchors', { 
      includeByteOffsets: true,
      maxResults: 5
    });
    expect(results.results[0]?.content).toBeDefined();
    validateSearchResults(results);
    logResults('P2 byte-offset-content-boundary', results);
  });

  // P3 - Medium: Standard FTS search
  it('P3 fts-standard-search', async () => {
    const results = await client.search('workspace', { 
      limit: 10,
      mode: 'combined'
    });
    expect(results.totalResults).toBeGreaterThan(0);
    validateSearchResults(results);
    logResults('P3 fts-standard-search', results);
  });

  // P4 - EASIEST: Empty query (returns all)
  it('P4 empty-query-all-results', async () => {
    const results = await client.search('', { 
      limit: 100,
      mode: 'combined'
    });
    expect(results.results.length).toBeLessThanOrEqual(100);
    validateSearchResults(results);
    logResults('P4 empty-query-all-results', results);
  });
});

// Helper function to log results for human review
function logResults(testName: string, results: any): void {
  const timestamp = new Date().toISOString();
  const logEntry = {
    timestamp,
    testName,
    totalResults: results.totalResults,
    resultsCount: results.results?.length || 0,
    query: results.query || '',
    strategy: results.strategy || 'unknown'
  };
  
  // Save to .anchor/logs for human review
  const fs = await import('fs');
  const path = await import('path');
  const logDir = path.join(process.env.PROJECT_ROOT || '.', '.anchor', 'logs', 'search-tests');
  const logFile = path.join(logDir, `${testName}-${timestamp.replace(/[:.]/g, '-')}.json`);
  
  fs.mkdirSync(path.dirname(logFile), { recursive: true });
  fs.writeFileSync(logFile, JSON.stringify(logEntry, null, 2));
}

function validateSearchResults(results: any): void {
  expect(results).toHaveProperty('results');
  expect(results).toHaveProperty('totalResults');
  expect(Array.isArray(results.results)).toBe(true);
  if (Array.isArray(results.results)) {
    results.results.forEach((r: any) => {
      expect(r).toHaveProperty('id');
      expect(r).toHaveProperty('source');
      expect(r).toHaveProperty('content');
    });
  }
}
```

---

## 3. Result Logging

### 3.1 Log Directory Structure

```
.anchor/logs/search-tests/
├── P0-semantic-search-complex-2026-05-18T12-00-00.json
├── P1-tag-search-multi-filter-2026-05-18T12-00-30.json
├── P2-byte-offset-content-boundary-2026-05-18T12-01-00.json
├── P3-fts-standard-search-2026-05-18T12-01-30.json
└── P4-empty-query-all-results-2026-05-18T12-02-00.json
```

### 3.2 Log Entry Format

```json
{
  "timestamp": "2026-05-18T12:00:00.000Z",
  "testName": "P0 semantic-search-complex",
  "totalResults": 42,
  "resultsCount": 10,
  "query": "authentication and authorization in Node.js best practices",
  "strategy": "semantic",
  "latencyMs": 234,
  "results": [
    {
      "id": "mol_abc123",
      "source": "anchor-engine-node/src/auth.ts",
      "content": "...",
      "score": 0.87
    }
  ]
}
```

---

## 4. Distillation Testing

### 4.1 Unseeded vs Seeded Distillation Tests

Tests should cover both unseeded (no prior context) and seeded (with context) distillation scenarios:

#### Unseeded Distillation Test

```typescript
it('distillation-unseeded', async () => {
  const results = await client.search('authentication', { 
    strategy: 'semantic',
    maxResults: 5
  });
  
  // Run distillation with no prior context
  const response = await fetch(`${API_BASE}/v1/memory/distill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      compounds: results.results.map(r => r.id),
      seed: null // No seed - unseeded
    })
  });
  
  const data = await response.json();
  expect(data.stats.compounds_processed).toBe(5);
  expect(data.output.path).toBeDefined();
  
  logDistillationResult('distillation-unseeded', data);
});
```

#### Seeded Distillation Test

```typescript
it('distillation-seeded-context', async () => {
  // First, get some context molecules
  const contextQuery = 'Node.js authentication';
  const results = await client.search(contextQuery, { 
    strategy: 'semantic',
    maxResults: 3
  });
  
  // Run distillation with seed context
  const response = await fetch(`${API_BASE}/v1/memory/distill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      compounds: results.results.map(r => r.id),
      seed: results.results[0].content, // Use first result as seed
      contextWindow: 512
    })
  });
  
  const data = await response.json();
  expect(data.stats.compounds_processed).toBe(3);
  expect(data.output.path).toBeDefined();
  expect(data.output.context).toContain(contextQuery);
  
  logDistillationResult('distillation-seeded-context', data);
});

function logDistillationResult(testName: string, data: any): void {
  const timestamp = new Date().toISOString();
  const logEntry = {
    timestamp,
    testName,
    stats: data.stats,
    outputPath: data.output.path,
    compressionRatio: data.stats.compression_ratio
  };
  
  const fs = await import('fs');
  const path = await import('path');
  const logDir = path.join(process.env.PROJECT_ROOT || '.', '.anchor', 'logs', 'distillation-tests');
  const logFile = path.join(logDir, `${testName}-${timestamp.replace(/[:.]/g, '-')}.json`);
  
  fs.mkdirSync(path.dirname(logFile), { recursive: true });
  fs.writeFileSync(logFile, JSON.stringify(logEntry, null, 2));
}
```

---

## 5. Search Algorithm Coverage Matrix

| Algorithm | Test Count | Pass Rate | Last Run | Notes |
|-----------|------------|-----------|----------|-------|
| Semantic (complex) | 0 | - | - | Needs implementation |
| Tag-based multi-filter | 0 | - | - | Needs implementation |
| Byte offset search | 0 | - | - | Needs implementation |
| FTS standard | 0 | - | - | Needs implementation |
| Empty query | 0 | - | - | Needs implementation |

---

## 6. Performance Targets

| Test Type | Max Latency | Budget Usage | Results Count |
|-----------|-------------|--------------|---------------|
| P0 Semantic (complex) | <3s | ~524k chars | ≤10 |
| P1 Tag multi-filter | <1s | ~64k chars | ≤10 |
| P2 Byte offset | <500ms | ~8k chars/atom | ≤5 |
| P3 FTS standard | <200ms | ~16-32k chars | ≤10 |
| P4 Empty query | <100ms | ~16-32k chars | unlimited (limited by limit param) |

---

## 7. Related Standards

- **Standard 028**: Unified Test Pipeline - Test orchestration framework
- **Standard 019**: Test Environment Consistency - Test setup requirements
- **Standard 004**: Streaming Search - SSE-based search implementation

---

**Last Updated:** 2026-05-18  
**Maintainer:** Anchor Engine Team