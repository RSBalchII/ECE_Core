# Smoke Test Plan — Live Data Testing

## Overview
This document outlines our comprehensive testing strategy to validate the Anchor Context Engine with live production data across all critical paths.

## Current Status
✅ **All tasks completed successfully!**
- All deprecated code removed
- Active services using proper `FALLBACK_DATA_DIR + 'notebook'`
- Build compiles without errors
- Test suite consolidation complete

## Testing Phases

### Phase 1: Unit Tests (100% Pass Rate)
```bash
# Core engine tests
pnpm test:unit
```

**Tests covering:**
- Search algorithm functionality (`engine/tests/unit/*.test.ts`)
- Memory management and GC operations
- Configuration validation schemas
- Security hardening components

### Phase 2: Integration Tests (Live-Fire)
Run against live production data to test:
- **Search Pipeline** (`engine/tests/integration/search-pipeline.test.ts`)
  - Semantic search → context inflation → result serialization
  - Byte offset tracking across pipeline stages
  
- **Radial Distillation** (`engine/tests/integration/radial-distiller.test.ts`)
  - Line deduplication with memory safety
  - Large document processing performance
  
- **MCP Server Integration** (`engine/tests/integration/mcp-server.test.ts`)
  - Tool execution and rate limiting (60 req/min)
  - Security boundary tests

### Phase 3: E2E Testing Setup
Set up comprehensive end-to-end testing:
```bash
cd tests/e2e/
node create-test-suite.js
```

Test scenarios:
- Full search-to-ingest pipeline
- Tag sanitization and enrichment
- WASM health checks and fallbacks
- Memory pressure and adaptive concurrency

### Phase 4: Performance Benchmarks
```bash
# Memory usage under load
node --max-old-space-size=2048 engine/bin/ingest --benchmark large-files/

# Search performance across datasets
node engine/bin/search-benchmark --datasets samples/*/search/

# WASM module loading performance
node --expose-wasm engine/bin/wasm-benchmark ./modules/*.wasm
```

## Live Data Testing Strategy

### Test Datasets Required:
1. **Large documents** (90MB+) for memory pressure testing
2. **Multiple file formats** (.md, .txt, .html, .jsonl)
3. **Real search queries** with various complexity levels
4. **Tag-heavy content** for sanitization validation
5. **Edge cases** (empty files, malformed data, etc.)

### Production Monitoring Integration:
- Performance monitoring during live loads
- Memory usage tracking under full load
- Error rate monitoring and alerting
- Circuit breaker testing in production environment

## Test Execution Commands

```bash
# Run all integration tests against live data
pnpm test:integration --live-data

# Performance benchmarks with real datasets
pnpm test:bio --datasets ./samples/biological/

# Memory pressure testing
node engine/bin/memory-pressure-test --threshold=80 --duration=300s

# Security boundary validation
pnpm test:security --target=https://api.anchor-context.engine.local
```

## Success Criteria
- ✅ All unit tests pass (100% success rate)
- ✅ Integration tests against live production data succeed
- ✅ Performance benchmarks meet targets
- ✅ Memory usage under thresholds
- ✅ Security boundaries properly validated
- ✅ WASM modules load correctly and fall back gracefully

## Documentation Links
- **[Migration Plan](../MIGRATION_PLAN.md)**
- **[Test Consolidation](../specs/tasks.md)**
- **[Standards](current-standards/)**
- **[API Route Map](API-ROUTE-MAP.md)**