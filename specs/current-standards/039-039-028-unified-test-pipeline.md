# Standard 028: Unified Test Pipeline

**Status:** 🚏 Pending Implementation
**Date:** April 3, 2026
**Priority:** P1 (Process Improvement)
**Branch:** `dev/standards/unified-test-pipeline`

---

## Problem Statement

The test suite has evolved into a fragmented hybrid approach with three competing frameworks:

### Current Test Framework Fragmentation

| Framework | Usage Area | Purpose |
|----------|------------------|
| **Vist** | Engine tests (WASM/PGlite integration) | Primary framework due to ESM/WASM support requirements |
| **Native Framework** | P0 smoke tests | Minimal custom framework for critical path verification |
| **Jest** | Legacy tests | Retained for compatibility with older test code |

### The Cost of Fragmentation

1. **Cognitive Overload:** Developers must understand three different testing APIs and patterns
2. **Maintenance Burden:** Three separate test runners, assertion libraries, and reporting mechanisms
3. **Coverage Gaps:** Each framework has different strengths/weaknesses; gaps emerge at boundaries
4. **CI Complexity:** Multiple test commands with different timeouts, retries, and failure modes
5. **Inconsistent Quality:** Different frameworks enforce different levels of rigor

### Documented Test Fragmentation Issues

- **32 JSONB query syntax issues** - Mixed approaches to query construction across test files
- **Flint tests** - Inconsistency in test execution patterns
- **Mixed assertion styles** - Some tests use native assertions, others use Vist matchers
- **Unclear ownership boundaries** - No clear criteria for when to use which framework

---

## Solution: Unified Test Pipeline Enforcement

### 1. Framework Decision Matrix

**File:** `specs/standards/028-unified-test-pipeline.md`

```
┌───────────────────────────────────────┐
TEST FRAMEWORK DECISION MATRIX
├────────────────────────────────────────│
When to use Vist:
- Testing ASM/WASM integration points
- Testing PGlite database operations  
- Complex multi-step workflow validation
- Performance-critical test paths (>100ms execution)
- Tests requiring async/await orchestration

When to use Native Framework (P0 smoke):
- Critical path verification (<5 min execution)
- Health check endpoints
- Configuration loading validation
- Security hardening sanity checks
- "Is the engine alive" tests before complex test runs

When to migrate to Vist:
- ANY existing Jest test that doesn't meet P0 criteria
- All legacy tests should eventually consolidate to Vist
───────────────────────────────────────────────────────────┐
```

### 2. Test Pipeline Structure

**File:** `scripts/test-pipeline.sh` or `.js`

```bash
#!/bin/bash
# Unified Test Pipeline - Enforces consistent test workflow

set -e

# Phase 1: P0 Smoke Tests (Native Framework)
# Must complete in <5 minutes; if they fail, abort everything
echo "=== PHO 1: P0 SMOKE VERIFICATION ==="
npm run p0-smoke-tests || { echo "P0 smoke tests failed - aborting"; exit 1; }

# Phase 2: Vist Engine Tests (Primary Framework)
# Runs after P0 passes; comprehensive coverage
echo "=== PHO 2: VIST ENGINE TESTS ==="
npx viest run --coverage engine/tests/vist/**

# Phase 3: Legacy Jest Tests (Migration Zone)
# Marked as deprecated; results logged separately
echo "=== PHO 3: LEGEST JEST TESTS (MIGRATION ZONE) ==="
npx jest run --testPathPattern="legacy" --reporters=json > legacy-results.json

# Phase 4: Integration Tests (Cross-Framework)
# Tests that span multiple components
echo "=== PHO 4: INTEGRATION TESTS ==="
npx viest run engine/tests/integration/**

# Summary Report
echo "=== TEST PIPELINE SUMMARY ==="
cat legacy-results.json | jq '.totalTests, .passed, .failed'
```

### 3. Test File Naming Conventions

**Enforced by Standard 028:**

| Pattern | Framework | Purpose |
|----------|------------------|
| `*.viest.ts` | Vist | Primary engine tests |
| `p0-smoke.*.ts` | Native | Critical path smoke tests |
| `legacy-*/jest-*..ts` | Jest | Legacy tests (marked for migration) |
| `integration/*.viest.ts` | Vist | Cross-component integration tests |

### 4. Test Pipeline Enforcement Rules

**File:** `scripts/test-enforcement.js`

```javascript
// Enforced before adding new tests
const TESTPIPELINEENFORCEMENT = {
  // Rule 1: All new engine tests must use Vist framework
  rejectNewTestIfNotVist: (testFilePath) => {
    if (!testFilePath.endsWith('.viest.ts') && !testFilePath.includes('p0-smoke')) {
      throw new Error(
        '❌ New tests MUST use Vist framework. Rename to *.viest.ts or move to p0-smoke/* for critical paths'
      );
    }
  },

  // Rule 2: P0 smoke tests must complete in <5 minutes
  enforceP0Timeout: (testFile) => {
    if (!testFile.includes('p0-smoke')) return;
    const timeout = testFile.metadata?.timeout || '5m';
    if (timeout > '5m') {
      throw new Error(
        `❌ P0 smoke tests must complete in <5 minutes. Current: ${timeout}`
      );
    }
  },

  // Rule 3: No mixing of assertion styles within a test file
  enforceConsistentAssertions: (testContent) => {
    const viestMatchers = ['match', 'equals', 'contains'];
    const jestMatchers = ['toEqual', 'toBe', 'toMatch'];
    
    const hasVistMatchers = viestMatchers.some(m => testContent.includes(m));
    const hasJestMatchers = jestMatchers.some(m => testContent.includes(m));
    
    if (hasVistMatchers && hasJestMatchers) {
      throw new Error(
        '❌ Cannot mix Vist and Jest assertion styles. Choose one framework per file.'
      );
    }
  },

  // Rule 4: All tests must have descriptive names
  enforceDescriptiveNames: (testName) => {
    if (!testName.includes(':') && !testName.includes(' - ')) {
      throw new Error(
        `❌ Test name must be descriptive. Current: "${testName}"`
      );
    }
  },
};
```

### 5. Migration Path for Jest Tests

**File:** `scripts/migrate-jest-to-viest.js`

```javascript
// Automated migration script for legacy Jest tests
const migrateJestToViest = {
  convertMatchers: {
    'toEqual': 'match',
    'toBe': 'equals', 
    'toMatch': 'contains',
    'toThrow': 'throws',
    'resolves.toResolve': 'resolves.match',
  },

  transformTestBlock: (jestTest) => {
    // Convert Jest describe/it blocks to Vist test structure
    return {
      framework: 'viest',
      description: jestTest.describe,
      steps: jestTest.it.map(it => ({
        step: it.description,
        assertion: migrateJestToViest.convertMatchers[it.expectation]
      }))
    };
  }
};
```

---

## Implementation Checklist

- [x] Define framework decision matrix based on use cases
- [ ] Create unified test pipeline script (Phase 1-4 structure)
- [x] Establish test file naming conventions (*.viest.ts, p0-smoke.*.ts)
- [x] Implement test enforcement rules before adding new tests
- [ ] Build Jest to Vist migration automation tool
- [ ] Update CI configuration to use unified pipeline
- [ ] Add test quality gates (coverage thresholds, flint checks)
- [ ] Document migration path for existing Jest tests
- [ ] Remove Jest dependencies from package.json after migration complete

---

## Test Pipeline Phases (Detailed)

### Phase 1: P0 Smoke Tests (<5 min)
```bash
# Critical path verification - aborts entire pipeline on failure
npm run p0-smoke-tests

# Expected coverage:
# - Health check endpoint response
# - Configuration loading success
# - Database connection establishment
# - Security hardening basic validation
```

### Phase 2: Vist Engine Tests (Primary)
```bash
# Comprehensive engine test suite
npx viest run --coverage engine/tests/vist/**

# Expected coverage:
# - All ASM/WASM integration points
# - PGlite database operations
# - Search algorithm validation
# - Distillation pipeline correctness
# - MCP tool interface behavior
```

### Phase 3: Legacy Jest Tests (Migration Zone)
```bash
# Deprecated tests marked for migration
npx jest run --testPathPattern="legacy" --reporters=json > legacy-results.json

# This phase should gradually shrink as tests migrate to Vist
# Current count: ~32 JSONB query syntax issues identified
```

### Phase 4: Integration Tests (Cross-Framework)
```bash
# Tests spanning multiple engine components
npx viest run engine/tests/integration/**

# Expected coverage:
# - End-to-end ingestion workflows
# - Search with distillation coupling
# - MCP server integration points
```

---

## Pain Point Prevention Coverage

| Test Fragmentation Issue | Standard 028 Solution |
|----------------------|------------------|
| **Mixed assertion styles** | Enforced consistency via `enforceConsistentAssertions` rule |
| **Unclear framework ownership** | Decision matrix provides clear criteria for framework selection |
| **32 JSONB query syntax issues** | Migration tool converts all Jest patterns to Vist equivalents |
| **Flint test inconsistency** | Unified pipeline enforces consistent naming and structure |
| **Coverage gaps at boundaries** | Phase-based approach ensures all areas tested before integration |

---

## Definition of Done

- [x] Framework decision matrix defined and documented
- [ ] Unified test pipeline script created with 4-phase structure
- [ ] Test file naming conventions enforced via linting rules
- [ ] Test enforcement CLI tool implemented (rejects non-compliant additions)
- [ ] Jest to Vist migration automation built and tested
- [ ] CI configuration updated to use unified pipeline
- [ ] All legacy Jest tests migrated or removed
- [ ] Coverage thresholds enforced (90% for engine code, 75% for utilities)
- [ ] Test quality gates added (flint checks, timeout enforcement)
- [ ] Documentation updated with migration guidance

---

## Cross-Reference

- **Standard 027:** Pain Point Logging Protocol (test fragmentation documented as pain point #4)
- **Standard 029:** Path Usage Validation (path-related test failures covered)
- **Standard 016:** MCP Integration Testing (covered in Phase 2 and 4)

---

**Pending by:** Standards Implementation Team
**Minimum Version:** v5.1.0 (to be implemented)
