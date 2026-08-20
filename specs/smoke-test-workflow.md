# Smoke Test Workflow

## Overview
This document outlines the smoke testing strategy for the Anchor Context Engine, covering P0 smoke tests and comprehensive test validation.

## Current Status ✅
All tasks completed successfully:
- Deprecated code removed: `MODELS_DIR`, `NOTEBOOK_DIR` → use `FALLBACK_DATA_DIR + 'notebook'`
- Active services updated: `radial-distiller`, `watchdog`, `search-utils`, `context-inflator`
- Legacy `/v1/models` endpoint cleaned up
- LLM provider verified as deprecated and unused

## P0 Smoke Tests (Critical Path)
These are the critical path tests that must pass to ensure system integrity:

### 1. Core Engine Functionality
```bash
# Unit tests - all passing ✅
ppnpm test:unit

# Integration tests against live data
pnpm test:integration --live-data

# Performance benchmarks
node engine/bin/memory-pressure-test --threshold=80 --duration=300s
```

### 2. Service Health Checks
- **Search Algorithm**: Semantic search, context inflation, result serialization
- **Radial Distillation**: Line deduplication, memory safety, output generation
- **MCP Server**: Tool execution, rate limiting (60 req/min)
- **Memory Management**: Adaptive concurrency, throttling, GC management

### 3. Security Boundary Validation
```bash
# Path traversal prevention
node engine/bin/security-test --target=https://api.anchor-context.engine.local

# Auth bypass audit
pnpm test:security --target=https://api.anchor-context.engine.local
```

## Live Data Testing Strategy

### Required Test Datasets:
1. **Large documents** (90MB+) for memory pressure
2. **Multiple file formats** (.md, .txt, .html, .jsonl)
3. **Real search queries** with varying complexity
4. **Tag-heavy content** for sanitization validation
5. **Edge cases**: empty files, malformed data

### Performance Targets:
- Unit tests: 100% pass rate
- Integration: Live-fire against production data
- Memory usage: Under thresholds during full load
- Security: All boundaries validated
- WASM: Modules load correctly with graceful fallbacks

## Documentation References
- **[Migration Plan](../MIGRATION_PLAN.md)**
- **[Test Consolidation](../specs/tasks.md)**
- **[Standards](current-standards/)**
- **[API Route Map](API-ROUTE-MAP.md)**