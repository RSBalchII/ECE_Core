# Standard 019: Test Environment Consistency

**Status:** Active  
**Date:** 2026-05-18  
**Category:** Testing  

## Problem

Test failures occurred because the test environment didn't match production behavior. Specifically, `getLatestEntryForHash()` returned incorrect data in tests because it was returning the last entry in the latest log file instead of filtering by query hash.

### Symptoms
- Test passed locally but failed in CI
- Function returned wrong data when called from tests vs production
- Log files existed but weren't found by test queries

## Root Cause Analysis

The function `getLatestEntryForHash(hash)` was implemented incorrectly:

```typescript
// ❌ WRONG IMPLEMENTATION
export function getLatestEntryForHash(hash: string): SearchLogEntry | null {
  // ... find latest log file ...
  const content = fs.readFileSync(path.join(LOGS_DIR, latestFile), 'utf-8');
  const lines = content.split('\n').filter(line => line.trim() !== '');
  const entries: SearchLogEntry[] = lines.map(l => JSON.parse(l));
  return entries.length ? entries[entries.length - 1] : null; // Returns LAST entry, not matching hash!
}
```

The function returned the last entry in the file regardless of whether it matched the requested hash.

## Solution

### Correct Implementation

```typescript
export function getLatestEntryForHash(hash: string): SearchLogEntry | null {
  ensureLogDir();
  const candidates = fs.readdirSync(LOGS_DIR)
    .filter(f => f.endsWith('.log') && f.includes('_search_'))
    .sort((a, b) => a.localeCompare(b));
  if (!candidates.length) return null;

  const latestFile = candidates[candidates.length - 1];

  try {
    const content = fs.readFileSync(path.join(LOGS_DIR, latestFile), 'utf-8');
    const lines = content.split('\n').filter(line => line.trim() !== '');

    // Find the entry matching our hash
    for (const line of lines) {
      try {
        const entry: SearchLogEntry = JSON.parse(line);
        if (entry.queryHash === hash) {
          return entry;
        }
      } catch {
        // Skip malformed lines
      }
    }

    // If not found, return null
    return null;
  } catch (e) {
    console.error('[SearchLogger] Failed to read log file:', e);
    return null;
  }
}
```

### Test Setup Requirements

**DO:**
- Initialize the logs directory before running tests that depend on it
- Use `process.env.ANCHOR_SEARCH_LOG = '1'` to enable logging in tests
- Call `logSearchResults()` with `{ verbose: true }` option for test reliability

**DON'T:**
- Assume log files exist when they don't
- Skip initialization steps that work in production but not in tests

### Example Test Setup

```typescript
import { logSearchResults, getLatestEntryForHash } from '../../src/services/search/search-results-logger';

describe('Engine Version Logging', () => {
  beforeEach(() => {
    // Enable search logging for this test
    process.env.ANCHOR_SEARCH_LOG = '1';
    clearAllLogsCache();
  });

  it('should include engineVersion in log metadata', () => {
    const query = 'anchor engine test';
    const hash = generateQueryHash(query); // Compute same hash as logger
    
    // Write a search result log entry
    logSearchResults(query, [/* mock results */], 
      { strategy: 'simple', totalResults: 1 },
      { verbose: true } // Ensure it writes to file
    );

    // Now we can query for the specific hash
    const entry = getLatestEntryForHash(hash);
    expect(entry).not.toBeNull();
    if (entry) {
      expect(entry.metadata.engineVersion).toBe('1.2.3');
    }
  });
});
```

## Prevention Checklist

### Before Writing Tests
- [ ] Identify all environment dependencies (directories, files, env vars)
- [ ] Set up those dependencies in `beforeEach` or test setup
- [ ] Match production behavior as closely as possible

### When Fixing Test Failures
- [ ] Ask: "Is this a real bug or just test setup?"
- [ ] If real bug: fix the code, not the test expectation
- [ ] If test setup issue: add proper initialization

### For Log/Storage Tests
- [ ] Use temporary directories that are cleaned up after tests
- [ ] Don't rely on persistent state between tests
- [ ] Mock external dependencies (database, file system) when appropriate

## Related Issues

- Issue: "getLatestEntryForHash returns null even after writing logs"
- Root cause: Function didn't filter by query hash, just returned last entry

## Related Standards

- Standard 017: Dependency Validation  
- Standard 028: Unified Test Pipeline

---

*Created: 2026-05-18*  
*Author: RS Balch II*