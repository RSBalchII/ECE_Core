# Issues Log — anchor-engine-node (v5.2 milestone session)

Running record of problems discovered during the 2026-08-19 → 2026-08-21 development and smoke-test sessions. Newest at top within each section. Statuses: OPEN / FIXED-PENDING-COMMIT / RESOLVED (workaround only) / VERIFIED-FIXED.

## Conventions
- Every issue gets an ID (`ISSUE-nn`), date found, status, symptom, root cause, evidence, and the planned or applied fix.
- Scratch/diagnostic files are never committed; this file is the durable tracker.
- Do not close an issue without new-run evidence (see VERIFIED-FIXED).
- Issues map to `specs/current-standards/` where a standard covers them; standards that contradict observed reality must be updated to match it.

## Open Issues

### ISSUE-17 — Distillation trigger silently kills the engine
- **Date found:** 2026-08-20 (smoke test) · **Status:** OPEN · **Standard:** 016 radial-distillation-v2, 022 operational-visibility
- **Symptom:** `POST /v1/distills/trigger` logged at 16:44:05; zero log lines after it; port dead by ~16:47. No crash trace captured.
- **Root cause (suspected):** radial distiller dereferences `atom.source_path` without existence guard — coding-notes atoms point to paths that may not resolve under the engine's working directory, producing undefineds that propagate into output writes or WASM heap growth until the process dies outside the error contract.
- **Evidence:** log gap after DISTILL_TRIGGER; known gap from earlier sessions ("distill path-string bug").
- **Fix plan:** (a) add `uncaughtException`/`unhandledRejection` guards in index.ts so crashes are logged before exit — codified as OPS-005 (crash observability, standard 022), which also covers the silent-death class behind ISSUE-16; (b) guard source_path resolution in radial-distiller-v2.

### ISSUE-18 — Search batch formatting throws on invalid atom timestamps
- **Date found:** 2026-08-20 · **Status:** OPEN · **Standard:** 007 data-integrity, 028 streaming-search
- **Symptom:** `density:` prefixed queries → HTTP 500 `RangeError: Invalid time value`.
- **Root cause:** result formatter calls `new Date(r.timestamp).toISOString()` unguarded; atoms whose timestamp parsed to a non-date (atomizer date regexes can capture ID-like strings) crash every batch touching them.
- **Fix plan:** valid-date check (`isNaN(d.getTime())`) with fallback before formatting.

### ISSUE-19 — Malformed `$null` filenames reach the ingestion pipeline
- **Date found:** 2026-08-20 · **Status:** OPEN (low severity) · **Standard:** 006 path-usage-validation
- **Symptom:** watchdog logged `coding-notes/$null - unsupported extension`. Harmless skip, but indicates a template/interpolation bug in ManualIngest's extra-path handling.
- **Fix plan:** trace where `$null` string is produced during ManualIngest; sanitize/validate before scheduling.

### ISSUE-20 — Enhanced watchdog status/validation API never implemented
- **Date found:** 2026-08-21 (audit of deleted live-fire-workflow-fix-plan.md) · **Status:** RESOLVED ✅ · **Standard:** 022 operational-visibility
- **Symptom:** plan proposed `validateIngestionPrerequisites`, `triggerManualIngestWithValidation`, `/v1/watchdog/status|validate|ingest` endpoints — none exist in code. Plan doc deleted; requirements preserved here.
- **Resolution (commit pending):** implemented the enhanced surface — `getWatcherStatus()` now returns a per-path report (`exists`/`accessible`/`fileCount`) for every watched directory, and a new `GET /v1/watchdog/validate` endpoint exposes that health summary alongside `/v1/watchdog/status`. Operators can now see at a glance which paths are misconfigured without digging through logs.

### ISSUE-21 — Path traversal sanitization absent from radial distiller and test-ui
- **Date found:** 2026-08-21 (audit of deleted security-update-plan.md) · **Status:** OPEN · **Standard:** 036 path-traversal-prevention
- **Symptom:** CodeQL alerts #98–#101 (`radial-distiller-v2.ts:1240,1263,1289,1315`) and #93–#96 (test-ui) — no `path.normalize()` + prefix check present.
- **Fix plan:** add sanitization guards per standard 036; re-run CodeQL to confirm closure.

### ISSUE-22 — handlebars version alerts may be stale lockfile noise
- **Date found:** 2026-08-21 · **Status:** OPEN (verify) · **Standard:** 013 dependency-validation
- **Symptom:** security plan demanded handlebars ≥4.8.0; lockfile pins 4.7.9 yet the package is not declared anywhere and no source imports it — likely transitive/stale entry.
- **Fix plan:** confirm via `pnpm why handlebars`; drop if unused, upgrade otherwise.

### ISSUE-23 — Compounds table removal migration never executed in fresh stores
- **Date found:** 2026-08-21 · **Status:** OPEN (deployment) · **Standard:** 018 distillation-output-storage
- **Symptom:** `schema-migration.sql:113` still creates the deprecated `compounds` table; spec.md marks it "being removed". Migration SQL exists (`migrate_compounds_to_molecules.sql`) but has not been run against current stores. Plan doc deleted; requirement preserved here.
- **Fix plan:** execute migration on wipe-and-rebuild cycles; then drop CREATE TABLE from schema-migration.sql so fresh stores never create it.

## Resolved (workaround applied)

### ISSUE-06 — Booting into a populated store overflows PGlite WASM heap
- **Date found:** 2026-08-21 · **Status:** RESOLVED via workaround · **Standard:** 011 ephemeral-database (**update required**)
- **Symptom:** `memory access out of bounds` on `SELECT path FROM sources` when starting the engine against a ~54k-atom store. Incremental ingestion itself stays within budget (ISSUE-12 cured).
- **Workaround:** every restart uses `wipe_on_startup=true`; clean-slate boot succeeds and re-ingestion completes inside 2–3 GB RSS (~732 MB peak observed).
- **Standard update needed:** 011 must document that populated stores exceeding WASM heap capacity cannot be booted — wipe-on-startup is the sanctioned operational path until a streaming-boot fix exists.

### ISSUE-16 — setup-user-config.mjs missing `fs` import (landmine)
- **Date found:** pre-session · **Status:** FIXED-PENDING-COMMIT · **Standard:** 005 configuration-validation
- Fix applied this session: added `import * as fs from "fs"` at line ~2. Verified by successful config regeneration before smoke test.

### ISSUE-13/14 — Git staging contamination + wrong-reference checkout (data loss)
- **Date found:** 2026-08-20 · **Status:** RESOLVED (process change) · **Standard:** n/a — process lesson, captured in memory
- Misfired `git add -p` staged files into the wrong commit; a subsequent `git checkout HEAD~1 --` silently reverted pending worktree modifications. Recovery via dist/ reconstruction + single-commit rebuild (`62f0b665`). Permanent rule: no interactive staging; never checkout-file-to-isolate-hunks.

## Historical (pre-session context)

### ISSUE-01 — OOM during full-corpus ingestion
- **Date found:** 2026-08-19 · **Status:** VERIFIED-FIXED · **Standard:** 008 memory-safe-ingestion, 010 pglite-memory-optimization
- Two independent full runs completed at RSS ~623–1094 MB with zero SIGKILL. Cure: streaming-GC watchdog + db-connection-serializer + memory-aware-executor (committed in `62f0b665`).

### ISSUE-02 — Config corruption / user_settings.json data-wipe
- **Date found:** 2026-08-19 · **Status:** RESOLVED · **Standard:** 004 configuration-management
- Corrupted/minimal config regenerated via patched setup script; valid API key restored, extra_paths set for smoke test.

### ISSUE-03 — `.gitignore:233` blanket `src/` rule silently excludes new source files
- **Date found:** 2026-08-19 · **Status:** RESOLVED (workaround) · **Standard:** 001 conventions
- Every untracked `engine/src/**` add requires `-f`; tracked modifications unaffected. Documented in memory and commit workflow; consider scoping the ignore rule to generated artifacts only if it recurs.

### ISSUE-05 — Harness limitations (compound heredoc commands rejected; foreground long-lived processes blocked)
- **Date found:** 2026-08-19 · **Status:** RESOLVED (workaround) · **Standard:** n/a — tooling lesson, captured in memory
- Write artifacts to files first, invoke separately; use `background=true` for servers.

## Deferred / accepted risks
- ISSUE-07: distill output volume vs WASM heap under combined corpora — monitor RSS during next full-corpus run; escalate only if SIGKILL recurs.
- ISSUE-15: scratch files (`smoke_test.py`, `.mjs` check scripts) remain untracked by design (doc_policy §2.2); delete after final validation pass.
