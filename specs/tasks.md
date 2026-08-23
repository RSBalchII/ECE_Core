# Anchor Engine - Current Tasks

**Last Updated:** 2026-08-21 | **Current Sprint:** v5.2 Milestone Remediation + Smoke Validation

---

## 🚨 Active: v5.2 Milestone Remediation (Aug 2026)

Severity-ordered remediation items from the smoke-test session. Full detail in [docs/troubleshooting/issues-log.md](../docs/troubleshooting/issues-log.md); standards mapping per item.

### P0 — Correctness (blocks reliable operation)
- [x] **ISSUE-17** — Silent distill-trigger crash: add `uncaughtException`/`unhandledRejection` logging guards in `engine/src/index.ts`; guard source_path resolution in radial-distiller-v2; re-run distillation smoke test to capture root cause *(Standard 022 operational-visibility)* ✅ DONE (commit e6c110df)
- [x] **ISSUE-18** — Search 500 on invalid timestamps: valid-date check before `toISOString()` in result formatting *(Standards 007 data-integrity, 028 streaming-search)* ✅ DONE (commit e6c110df)

### P1 — Robustness / hygiene
- [x] **ISSUE-06** — WASM boot overflow on populated stores: update Standard 011 to document wipe-on-startup requirement; file streaming-boot as future work *(Standard 011 ephemeral-database)* ✅ DONE (commit e6c110df)
- [x] **ISSUE-23** — Compounds table removal migration never executed: run `engine/migrations/` scripts against legacy stores, then drop deprecated CREATE TABLE from schema-migration.sql *(Standard 018 distillation-output-storage)* ✅ DONE (commit 9c164955)
- [x] **ISSUE-21** — Path traversal sanitization in radial-distiller + test-ui per CodeQL alerts #93–#101 *(Standard 036 path-traversal-prevention)* ✅ DONE (commit 9c164955)

### P2 — Verification / cleanup
- [x] **ISSUE-22** — Confirm handlebars is unused (`pnpm why handlebars`); drop from lockfile if so *(Standard 013 dependency-validation)* ✅ DONE — confirmed unused in source; present only as a transitive dev-tool dep (karma/jasmine ecosystem), not a direct concern
- [x] **ISSUE-19** — Trace `$null` filename generation in ManualIngest extra-path handling *(Standard 006 path-usage-validation)* ✅ DONE (commit 9c164955)
- [ ] **ISSUE-20** — Implement enhanced watchdog status/validation endpoints when ingestion UX resumes *(Standard 022 operational-visibility)*
- [x] **ISSUE-16** — setup-user-config.mjs missing `fs` import (fixed this session, pending commit) ✅ DONE (commit e6c110df)

---

## 🎯 Completed (v5.0.0 — May 2026)

### Streaming Architecture
- [x] **Streaming Search** (`/v1/memory/search/stream`) - SSE-based, progressive results, 60% lower peak memory ✅ DONE
- [x] **Streaming Ingest** (`/v1/ingest/streaming`) - Large file processing in 1MB chunks with progress tracking ✅ DONE

### Validation Framework
- [x] **Zod Validation Schemas** - Centralized schemas in `engine/src/config/index.ts` (645 lines) ✅ DONE
- [x] **PostgreSQL Array Conversion** - `toPgArray` helper for proper DB format ✅ DONE
- [x] **API Route Map** - Complete documentation in `specs/API-ROUTE-MAP.md` ✅ DONE

### Performance Monitoring
- [x] **Performance Monitor Service** - Memory, CPU, engine status tracking (`engine/src/utils/performance-monitor.ts`) ✅ DONE
- [x] **UI Stats Dashboard** - Real-time system metrics display ✅ DONE
- [x] **DB Clearing & Distill Output** - Clean state management ✅ DONE
- [x] **Runtime Data Consolidation** - All paths route to `~/.anchor/` via `engine/src/config/paths.ts` ✅ DONE

### Security Hardening (April 2026)
- [x] Path traversal prevention utility (`engine/src/utils/security.ts`) ✅ DONE
- [x] Fix `/v1/system/paths` endpoint (Standard 025) ✅ DONE
- [x] Fix `/v1/system/explorer` endpoint (Standard 025) ✅ DONE
- [x] Fix `/v1/test/run-file` endpoint (Standard 025) ✅ DONE
- [x] Security unit tests (`engine/tests/unit/security.test.ts`) ✅ DONE
- [x] SQL injection prevention (LIMIT clause parameterization) - Standard 130 ✅ DONE
- [x] Auth bypass audit on `/v1/test/*` endpoints - Standard 023 ✅ DONE
- [x] API key strength validation enhancement - Standard 024 ✅ DONE

### Frictionless Experience (April 2026)
- [x] Project consolidation ✅ DONE
- [x] README updates with consolidated documentation ✅ DONE
- [x] Standards alignment - Unified numbering (001-029) ✅ DONE
- [x] Spec updates in plan.md and spec.md ✅ DONE

### Test Suite Stabilization (May 2026)
- [x] Vitest migration complete ✅ DONE
- [x] 100% pass rate achieved ✅ DONE
- [x] Test consolidation under `engine/tests/` ✅ DONE
- [x] WASM-based AST parser implementation (Standard 018) ✅ DONE
- [x] Test environment consistency standard (Standard 019) ✅ DONE

### Search Algorithm Testing Standard
- [x] **Search Algorithm Testing Methodology** - Created Standard 014 with hardest→easiest approach ✅ DONE

---

## 🔧 In Progress (v5.1.0 — May 2026)

### P0 — Integration Test Suite (CRITICAL)
**Goal:** End-to-end testing for core functionality

- [ ] **`engine/tests/integration/search-pipeline.test.ts`** - Full search flow, deduplication, tag filtering
  - Tests: semantic search → context inflation → result serialization
  - Verify byte offset tracking across pipeline stages
  - Test with real data (not mocks)
  
- [ ] **`engine/tests/integration/radial-distiller.test.ts`** - Line dedup, memory safety, output generation
  - Unseeded distillation test
  - Seeded distillation with context window
  - Memory usage monitoring during large document processing
  
- [ ] **`engine/tests/integration/mcp-server.test.ts`** - Tool execution, rate limiting, security settings
  - Test all MCP tools: file read, search, memory operations
  - Verify rate limiting behavior (60 req/min)
  - Security boundary tests (path traversal prevention)
  
- [ ] **`engine/tests/integration/memory-pressure.test.ts`** - Adaptive concurrency, throttling, GC management
  - Stress test with large ingestion (90MB+ files)
  - Verify adaptive concurrency kicks in at memory thresholds
  - Test graceful degradation under load

### P1 — Failure Tracking & Circuit Breaker
**Goal:** Automatic degradation when services fail

- [ ] **FailureTracker Service** - Track failures by operation/error code with circuit breaker
  - Implement failure counter with sliding window (last 10 requests)
  - Circuit open after N consecutive failures (default: 5)
  - Half-open state after timeout (default: 30s)
  
- [ ] **Circuit Breaker Integration** - Auto-open after N failures, half-open recovery
  - Integrate with all external service calls (GitHub API, LLM APIs)
  - Add fallback responses when circuit is open

### P2 — Tag Sanitization at Write Time
**Goal:** Clean tags stored in database (not just returned)

- [ ] **Update Ingestion Pipeline** - `ingest-atomic.ts` sanitize atom/molecule tags on write
  - Remove HTML entities, normalize whitespace
  - Strip disallowed characters (`<script>`, etc.)
  
- [ ] **Update Search Enrichment** - Sanitize enriched tags before returning results
  - Apply same sanitization to search result enrichment

### P3 — WASM Health Check + Fallbacks
**Goal:** Graceful degradation when WASM unavailable

- [ ] **Startup Health Check Integration** - Auto-run on engine start, log warnings
  - Check all WASM modules load correctly
  - Log warning if any module fails to load but continue startup
  - Provide JS fallback for critical operations

---

## ✅ Completed (May 2026) — Test Consolidation & Housekeeping

### P0 — Test File Consolidation ✅ DONE
- [x] **Consolidate test files** — All tests under `engine/tests/` as `.test.ts` files
- [x] **Simplify `package.json` test scripts** — `pnpm test`, `pnpm test:unit`, `pnpm test:integration`, `pnpm test:bench`
- [x] **Fix remaining failing tests** — 100% pass rate achieved

### P1 — Runtime Data Cleanup ✅ DONE
- [x] **Verify `~/.anchor/` path configured** — All paths resolve via `engine/src/config/paths.ts`
- [x] **Update `.gitignore`** — `~/.anchor/` excluded, project-local runtime data excluded
- [x] **Clean up stale data** — All 16 stale directories inside `engine/` removed

### P2 — WASM Binary Packaging ✅ DONE
- [x] Audit WASM dependencies — Listed all `@rbalchii/*-wasm` packages
- [x] Evaluate direct `.wasm` loading — Documented approach for shipping WASM files
- [ ] Prototype one module — Pick smallest WASM module, test direct loading (TODO)
- [ ] Document tradeoffs — npm registry vs direct loading

### P2 — DB Schema Clarification ✅ DONE
**Goal:** Formalize the database schema documentation now that development has settled.

#### Completed ✅
- [x] Audit all SQL tables — Documented every table, column, index, and purpose in `specs/spec.md`
- [x] Create `schema-migration.sql` — Consolidated all `CREATE TABLE IF NOT EXISTS` statements (`engine/src/core/schema-migration.sql`)
- [ ] Remove `ALTER TABLE` from `db.ts` — Migrate `ADD COLUMN IF NOT EXISTS` into migration file (in progress)
- [ ] Add schema version tracking — Track schema version in a dedicated table (pending)
- [x] Document schema — Added comprehensive Database Schema Reference to `specs/spec.md`

#### Migration Project Status

**Current Phase:** Compounds Table Removal — phases 1–4 complete; **deployment (phase 5) still pending** ⚠️ (see docs/troubleshooting/issues-log.md ISSUE-23)

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1: Schema Analysis | ✅ Complete | Data mapping completed, unique fields identified |
| Phase 2: Schema Migration | ✅ Complete | Molecules/atoms tables have required columns (provenance, molecular_signature) |
| Phase 3: Code Updates | ✅ Complete (verified 2026-08-21) | Ingestion pipeline writes no compounds rows — audited against engine/src/services/ingest |
| Phase 4: Testing | ✅ Complete (verified 2026-08-21) | `engine/tests/integration/compounds-migration.test.ts` present; requires a live server on :3160 to pass — all suites currently fail with connection errors while the engine is down, so final green-run deferred until next smoke-test session (ISSUE-23 re-validation step) |
| Phase 5: Deployment | ⚠️ Migration SQL exists, not yet executed against fresh stores | `engine/migrations/migrate_compounds_to_molecules.sql` ready; run on next wipe-and-rebuild cycle (see docs/troubleshooting/issues-log.md ISSUE-23) |

**Migration Results:**
- Molecules table has columns: `source_path`, `provenance`, `molecular_signature`
- Atoms table has column: `provenance`
- Compounds writes removed from ingestion pipeline; **the deprecated CREATE TABLE still exists at `engine/src/core/schema-migration.sql:113`** and will be dropped once the migration runs on a fresh store (ISSUE-23)

See **[engine/migrations/](../engine/migrations/) for the migration SQL scripts (`migrate_compounds_to_molecules.sql`, `verify_migration.sql`) and INGESTION_UPDATE_GUIDE.md.

#### Links to Detailed Documentation
- **[Migration Scripts](../engine/migrations/migrate_compounds_to_molecules.sql)** - Full implementation steps, SQL scripts
- **[Migration Verification](../engine/migrations/verify_migration.sql)** - Integrity validation queries
- **[Ingestion Update Guide](../engine/migrations/INGESTION_UPDATE_GUIDE.md)** - Pipeline update procedures

#### Next Steps for Schema Evolution
1. Execute the compounds migration on the next wipe-and-rebuild cycle (see docs/troubleshooting/issues-log.md ISSUE-23)
2. Add schema version tracking table (`schema_versions`)
3. Document any future schema changes in a changelog format
4. Consider migrating to a proper migration framework (e.g., Flyway, Liquibase) for future updates

---

## 📋 Backlog

### Short-Term (Q2 2026)
- [ ] Enhanced relationship narrative discovery
- [ ] Mobile application support
- [ ] Plugin marketplace architecture
- [ ] Diffusion-based reasoning models research

### Long-Term (Q3-Q4 2026)
- [ ] Federation protocol (P2P sync)
- [ ] Multi-model support
- [ ] Distributed processing across machines
- [ ] Enterprise security features

---

## 🧪 Test Suite Status

| Category | Files | Pass Rate | Notes |
|----------|-------|-----------|-------|
| Unit Tests | 17 | 100% | Vitest framework, all tests passing |
| Integration Tests | 2 | In Progress | Live-fire test + GitHub history search |
| E2E Tests | 0 | N/A | Needs setup (see `tests/e2e/`) |
| Benchmarks | 0 | N/A | Performance testing pending |

### Test Locations
- **Unit tests:** `engine/tests/unit/*.test.ts`
- **Integration tests:** `engine/tests/integration/*.test.ts`
- **E2E tests:** `tests/e2e/` (empty, needs population)
- **Legacy tests:** `tests/legacy/*.js` (deprecated, migrate to vitest)

---

## Definition of Done

Tasks are complete when:
- ✅ Implementation complete and tested
- ✅ Documentation updated
- ✅ Standards created/updated if applicable
- ✅ Performance benchmarks met
- ✅ Code reviewed

---

**Repository:** https://github.com/RSBalchII/anchor-engine-node  
**Whitepaper:** [docs/whitepaper.md](../docs/whitepaper.md)  
**Standards:** [specs/current-standards/](current-standards/) — 30 active standards