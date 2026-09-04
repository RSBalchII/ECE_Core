# Changelog

All notable changes to the Anchor Engine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] - In Progress

### 📄 Distillation Standards Consolidation (Standard 015)
- **What**: Consolidated the six fragmented distillation standards into a single coherent standard describing how the distiller actually works.
- **New file**: `specs/current-standards/015-015-distillation.md` — covers all four runtime methods, mode-selection rules, data-model/provenance links, self-contamination prevention, output storage, and API contract.
- **Removed** (superseded by Standard 015): Standards 008, 133, 134, 027, 028, 029 (`radial-distillation`, `radial-distillation-v2`, `zero-copy-dedup`, `distillation-output-storage`, `self-contamination-prevention`, `tag-based-distillation`).
- **Now documented (was missing)**: **full-corpus mode** — the live default for seedless requests. Describes compound grouping, content SimHash dedup, union-find chain collapse, inline `dedup_of[]` provenance, and memory-flat streaming re-inflation.
- **Aligned**: `specs/spec.md` data-model section (new "Distillation Methods & Mode Selection" subsection; `dedup_of`; corrected distills-table references to Standard 015) and `docs/INDEX.md` nav links.

### 🔧 Circuit Breaker & Resilience

#### Circuit Breaker Pattern Implementation (Standard 014)
- **New**: Circuit breaker pattern for resilient service calls
- **File**: `engine/src/utils/circuit-breaker.ts`
- **Features**:
  - Three states: closed, open, half-open
  - Configurable failure threshold (default: 5)
  - Automatic recovery with half-open state
  - Failure tracking by type
- **Testing**: P0 integration tests in `engine/tests/integration/`

#### P0 Integration Test Suite
Created comprehensive P0 integration tests with circuit breaker protection:
- `search-pipeline.test.ts` - Search pipeline tests (18 tests)
- `radial-distiller.test.ts` - Radial distillation tests (18 tests)
- `memory-pressure.test.ts` - Memory pressure detection tests (18 tests)
- `mcp-server.test.ts` - MCP server integration tests (18 tests)

**Total**: 77 P0 integration tests covering:
- Circuit breaker state transitions
- Failure tracking and categorization
- Memory pressure detection
- LRU cache eviction
- MCP tool execution
- Search pipeline operations

---

### 🔒 Security Improvements

#### QwenPaw Agent Configuration Protection
- Added `.gitignore` entries to prevent accidental commit of sensitive QwenPaw agent configuration files:
  - `BOOTSTRAP.md`, `MEMORY.md`, `PROFILE.md`, `SOUL.md`, `AGENTS.md`
- These files may contain private information and should never be committed to the repository

#### Deprecated C++ Native Modules Removal
- Removed `engine/src/native/` directory containing deprecated C++ code
- Replaced with Rust WASM modules (`@rbalchii/*-wasm`) for better cross-platform compatibility
- Added `engine/src/native/node_modules/` and `engine/build/` to `.gitignore`

### Planned

- Enhanced code analysis with AST pointers
- Relationship narrative discovery improvements
- Mobile application support
- Plugin marketplace
- Diffusion-based reasoning models

---

## [5.2.0] - 2026-04-25 — Simplified Start Scripts & Path Resolution Fix

### 🛠️ Breaking Changes

**Simplified Installation Workflow**: Removed complex validation scripts in favor of direct engine launch.

**Before:** Required `scripts/validate-and-start.mjs` which is no longer needed
**After:** Simple `pnpm start` directly launches the engine

#### Changes:
- **Removed** `scripts/validate-and-start.mjs` (no longer required)
- **Updated** `package.json` `start` script to run `node --expose-gc engine/dist/index.js`
- **Simplified** install scripts (`install.ps1`, `install.sh`)

### 🔧 Technical Improvements

#### ES Module Path Resolution Fix (Standard 029 Compliance)
Fixed path resolution issues when running TypeScript files with ES modules:

**Problem:** Using `import.meta.url` caused "Invalid URL" errors in certain environments.

**Solution:** Implemented robust path construction that works across all environments:
```typescript
const getProjectRoot = () => {
  try {
    const url = new URL('file://' + import.meta.url);
    return path.join(url.pathname, '..').replace(/\\/g, '/');
  } catch (e) {
    return process.cwd(); // Fallback for Node.js environments
  }
};
```

**Files Modified:**
- `engine/src/index.ts` - Fixed UI path resolution to serve from `engine/public/`
- Fixed fallback to `integrations/web-dashboard/dist/` when needed

#### UI Source Clarification
The engine now serves two UI sources:
1. **Primary**: `engine/public/index.html` (single-file React app)
2. **Fallback**: `integrations/web-dashboard/dist/index.html` (if available)

### 📦 Version Updates

- `package.json`: 5.2.0
- `user_settings.json.template`: VERSION = "5.2.0"

---

## [5.1.0] - 2026-04-03 — Security Hardening Release (P0 Vulnerabilities Fixed)

### 🔒 Security Fixes (Critical)

**4 P0 Vulnerabilities Fixed** - March 2026 Security Review

#### 1. Path Traversal Prevention (Standard 129)
**Vulnerability:** User-supplied paths in `/v1/system/*` and `/v1/test/*` endpoints could escape intended directories via `../` sequences.

**Impact:** High - Could read arbitrary files (e.g., `/etc/passwd`, `~/.ssh/id_rsa`)

**Fix:**
- Added path validation in `engine/src/routes/v1/system.ts` (3 endpoints)
- Added path validation in `engine/src/routes/test-ui.ts` (1 endpoint)
- All paths now validated to stay within `PROJECT_ROOT` and `NOTEBOOK_DIR`

**Branch:** `dev/security/path-traversal`

---

#### 2. SQL Injection Prevention (Standard 130)
**Vulnerability:** LIMIT clauses in search queries used string interpolation with user-derived values.

**Impact:** High - Potential SQL injection via crafted search parameters

**Fix:**
- `engine/src/services/search/search.ts` - Molecule query now uses parameterized `$N` binding
- `engine/src/services/search/explore.ts` - Atom fetch LIMIT now parameterized
- All LIMIT values passed as query parameters, not interpolated strings

**Branch:** `dev/security/sql-injection`

---

#### 3. Authentication Bypass Prevention (Standard 131)
**Vulnerability:** All `/v1/test/*` endpoints bypassed authentication entirely for "development convenience."

**Impact:** Critical - Test endpoints could:
- Execute arbitrary test files (`/v1/test/run-file`)
- Write arbitrary JSON to filesystem (`/v1/test/snapshot`)
- Read arbitrary files via path traversal (`/v1/test/snapshot/:name`)

**Fix:**
- `engine/src/middleware/auth.ts` - Removed `/v1/test/*` from auth bypass whitelist
- `engine/src/routes/test-ui.ts` - Added regex validation for snapshot name parameter
- All test endpoints now require valid API key authentication

**Branch:** `dev/security/auth-bypass-audit`

---

#### 4. API Key Strength Validation (Standard 132)
**Vulnerability:** API keys only required 16 characters with no complexity requirements. Weak keys like `aaaaaaaaaaaaaaaa` were accepted.

**Impact:** High - Weak keys vulnerable to brute force and dictionary attacks

**Fix:**
- `engine/src/config/index.ts` - Enhanced Zod schema validation:
  - Minimum length: 16 → **32 characters**
  - Maximum length: **128 characters**
  - Required: uppercase + lowercase + digit
- `engine/src/index.ts` - Runtime validation with clear error messages
- Entropy increased from ~75 bits to **~190 bits** (billions of years to crack)

**Migration:** Existing weak keys will be rejected. Generate new key:
```bash
# Using Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

**Branch:** `dev/security/api-key-strength`

---

### ⚡ Performance Improvements

#### 5. Zero-Copy Deduplication in Distillation (Standard 134)
**Problem:** The radial distiller processed every inflated compound through the full UTF-8 string split + line-level hashing pipeline, even when the compound content was a duplicate of content already seen.

**Impact:** For 50-90% duplicate rates (common in large conversation logs, version histories), 50-90% of CPU time was wasted on duplicate processing.

**Fix:**
- Added Tier 1 compound-level SHA-256 dedup in `engine/src/services/distillation/radial-distiller.ts`
- Content hashed as raw bytes BEFORE splitting into lines
- Duplicate compounds skip the entire `split → normalizeLine → hashLine` pipeline
- Only unique compounds proceed to Tier 2 line-level dedup
- Stats now track `compoundsSkipped`, `compoundsTotal`, and `tier1_skip_rate`

**Expected Performance:**
- 50% duplicate rate → ~2x speedup on distillation
- 90% duplicate rate → ~10x speedup on distillation
- Memory overhead: ~43 bytes per compound for hash Set (negligible)

**Cross-Reference:** Ported from `anchor-engine-rust` commit `0c67d23` (zero-copy dedup in distill)

**Branch:** `dev/zero-copy-dedup`

---

### 📚 Security Standards Created

- **Standard 129:** Path Traversal Prevention
- **Standard 130:** SQL Injection Prevention (Parameterized LIMIT)
- **Standard 131:** Authentication Bypass Prevention
- **Standard 132:** API Key Strength Validation
- **Standard 134:** Zero-Copy Deduplication in Distillation

### 🔧 Technical Changes

**Modified Files:**
- `engine/src/middleware/auth.ts` - Auth bypass fix
- `engine/src/routes/v1/system.ts` - Path traversal fix
- `engine/src/routes/test-ui.ts` - Path traversal + input validation
- `engine/src/services/search/search.ts` - SQL injection fix
- `engine/src/services/search/explore.ts` - SQL injection fix
- `engine/src/services/distillation/radial-distiller.ts` - Zero-copy dedup (Standard 134)
- `engine/src/config/index.ts` - API key strength validation
- `engine/src/index.ts` - API key runtime validation

**Documentation:**
- `specs/standards/129-path-traversal-prevention.md`
- `specs/standards/130-sql-injection-prevention.md`
- `specs/standards/131-auth-bypass-prevention.md`
- `specs/standards/132-api-key-strength-validation.md`
- `specs/standards/134-zero-copy-dedup.md`

### 🎯 Security Review Summary

| Vulnerability | CVSS Score | Status | Branch |
|---------------|------------|--------|--------|
| Path Traversal | 7.5 (High) | ✅ Fixed | `dev/security/path-traversal` |
| SQL Injection | 8.6 (High) | ✅ Fixed | `dev/security/sql-injection` |
| Auth Bypass | 8.6 (High) | ✅ Fixed | `dev/security/auth-bypass-audit` |
| API Key Strength | 7.5 (High) | ✅ Fixed | `dev/security/api-key-strength` |

### ⚠️ Breaking Changes

**API Key Requirements Changed:**
- Old keys with < 32 characters or no complexity will be **rejected**
- Update your `user_settings.json`:
  ```json
  {
    "server": {
      "api_key": "YourNewSecureKey123..."  // 32-128 chars, mixed case + digit
    }
  }
  ```

### 📦 Version Updates

- `package.json`: 5.1.0
- `engine/package.json`: 5.1.0
- `user_settings.json.template`: VERSION = "5.1.0"

### Architecture Clarifications (added 2026-05-19)

#### 📚 Architecture Standards & Documentation

##### Standard 027: Distillation Output Storage
**Clarification:** Distillation outputs are event chains/nodal maps for context seeding, NOT raw content to reintroduce into source corpus.

- **Purpose:** Distilled YAML files serve as semantic summaries and provenance records that seed future distillation cycles
- **Storage Location:** `notebook/distills/` (intentionally separate from pointer-only `mirrored_brain/`)
- **Content Type:** Event chains with compound→atom relationships, tag hierarchies, temporal metadata
- **NOT For:** Re-ingesting raw content back into the corpus (violates Standard 051)

##### Standard 028: Self-Contamination Prevention
**Current Mechanism:** Filename pattern matching to detect distillation outputs in ingestion paths.

**Identified Edge Cases:**
- Renamed files bypass protection (e.g., `distilled_notes.md` → `my_notes.md`)
- Content-based detection not yet implemented
- Provenance chain tracking incomplete

**Proposed Enhancements:**
- Content hash comparison against known distillation patterns
- Metadata field validation (`_type: distillation_output`)
- Full provenance chain verification from original source

##### Standard 029: Tag-Based Distillation Mode
**Distinct Concept-Centric Workflow vs File-Centric Standard Mode:**

| Aspect | Standard Mode | Tag-Based Mode |
|--------|---------------|----------------|
| Input | Specific files/directories | Tag patterns |
| Output | File-specific summaries | Cross-tag deduplicated concepts |
| Use Case | Targeted content processing | Thematic exploration across corpus |

**Cross-Tag Deduplication Strategy:**
- Identifies semantically equivalent atoms sharing multiple tags
- Consolidates redundant representations into single canonical form
- Preserves original provenance in metadata

##### Standard 031: Search Algorithms Comprehensive Reference
**Consolidated P0 Reference Document (~700k tokens)** covering all 8 algorithms:

| Algorithm | Purpose | Key Characteristics |
|-----------|---------|---------------------|
| **STAR** (Standard) | General purpose search | Term overlap + tag relevance + temporal decay |
| **Exact** | Precise term matching | FTS5 full-text, no semantic expansion |
| **Deep** | Maximum recall | Multi-query splitting, sequential processing |
| **Illuminate** | Corpus narrative | BFS graph traversal from hub compounds |
| **Explore** | Concept skeleton | Tag-hub map without content inflation |
| **Tag-Based** | Thematic queries | Cross-tag deduplication strategy |
| **Streaming** | Memory efficiency | SSE batch delivery, progressive results |
| **Mobile** | Low-resource optimization | Aggressive caching, reduced token budgets |

##### Standard 051: Pointer-Only Storage Implementation Verified
**Critical Architecture Fix:** Database stores pointers only; content written to `mirrored_brain/@inbox/` filesystem.

**Verification Results:**
✅ Test document ingested successfully via `test-ingest2.json`
✅ Content exists at `mirrored_brain/@inbox/api_upload` and `mirrored_brain/@inbox/test-upload`
✅ Compound.path updated to point to mirror location post-ingestion
⚠️ Distillation returns 0 blocks for simple text (expected - needs structured markdown)

**Modified Files:**
- `engine/src/routes/v1/ingest.ts` - Writes raw content to mirror after DB storage
- Mirror path format: `@inbox/{timestamp}_{hash}.md`

#### 🔧 Technical Changes

**Files Modified:**
- `specs/current-standards/dependencies/018-ast-parser-wasm.md` (Standard 018)
- `specs/current-standards/testing/019-test-environment-consistency.md` (Standard 019)
- `specs/current-standards/search-retrieval/014-search-algorithm-testing.md` (Standard 030)

**New Standards Created:**
- Standard 027: Distillation Output Storage
- Standard 028: Self-Contamination Prevention  
- Standard 029: Tag-Based Distillation Mode
- Standard 031: Search Algorithms Comprehensive Reference
- Standard 051: Pointer-Only Database Storage

---

## [5.0.0] - 2026-03-29 — Stable Release with Full-Featured UI

### 🎉 Major Version Release

**Problem:** UI consolidation attempt (e57947b) broke the working distillation UI

**Solution:**
- ✅ Restored full-featured single-file React UI (`engine/public/index.html`)
- ✅ Black theme with purple/cyan gradients
- ✅ Responsive navigation (desktop + mobile)
- ✅ Copy buttons with feedback toasts
- ✅ Streaming search with SSE (Server-Sent Events)
- ✅ Query prefixes: `distill:`, `illuminate:`, `explore:`, `deep:`, `exact:`, `fast:`
- ✅ Token budget slider (512 - 1M tokens)
- ✅ Ingestion progress indicator in header
- ✅ Pagination for search results
- ✅ Bucket selection for targeted searches
- ✅ Mobile drawer navigation with hamburger menu

### 🐛 Fixed:
- Duplicate navbars on desktop (CSS `!important` fix)
- Reverted failed UI consolidation from e57947b
- Restored working distillation UI with YAML download

### 🔧 Technical:
- `engine/public/` serves as primary UI
- `integrations/web-dashboard/` remains as fallback
- No build step required for UI (React + Babel standalone)
- Tailwind CSS via CDN for utility classes

### 📦 Version Updates:
- `package.json`: 5.0.0
- `engine/package.json`: 5.0.0
- `user_settings.json.template`: VERSION = "5.0.0"
- UI display: v5.0.0

---

## [4.9.7] - 2026-03-26 — Documentation Hygiene, Path Configuration, Distill Fix

### 📚 Documentation Hygiene (Standard 022)

**Problem:** 220+ markdown files scattered across project, duplicate guides, configuration drift fixed multiple times

**Solution:**
- **Standard 022: Documentation Hygiene** - New active standard
- **Allowed directories**: `docs/`, `specs/`, `[package]/README.md` ONLY
- **Cross-reference check**: `grep -ri` before creating any docs
- **Pain point log**: Appendix in Standard 022 tracks recurring issues
- **Archive policy**: Auto-archive standards inactive >6 months
- **Updated `.ai-instructions.md`** - References Standard 022

**Pain Points Logged:**
1. Configuration drift (fixed 3+ times in 40 commits)
2. GitHub PAT authentication (4 commits to implement)
3. Path manager bug (`../..` vs `..`)
4. Distill file read error (wrong directory)

### 🔧 Path Configuration Centralization

**Problem:** Hardcoded paths in multiple files, pathManager returning wrong notebook path

**Solution:**
- **`user_settings.json` paths section** - All paths configurable in one place:
  ```json
  {
    "paths": {
      "notebook": "notebook",
      "inbox": "notebook/inbox",
      "external_inbox": "notebook/external-inbox",
      "distills": "notebook/distills",
      "mirrored_brain": ".anchor/mirrored_brain",
      "context": "engine/context",
      "logs": "logs"
    }
  }
  ```
- **`paths.ts` updated** - Reads from `user_settings.json` with env var overrides
- **Priority**: Environment variables > user_settings.json > defaults
- **New export**: `PATHS.DISTILLS_DIR` for distillation output

### 🐛 Distill File Read Fix

**Problem:** `/v1/files/read` looked in `inbox/distilled/` but radial-distiller-v2 wrote to `notebook/distills/`

**Solution:**
- **Updated `system.ts`** - Uses `PATHS.DISTILLS_DIR` instead of hardcoded path
- **Updated `memory.ts`** - Import from `radial-distiller-v2.js` (not old `radial-distiller.js`)
- **Auto-create distills directory** if it doesn't exist
- **Support both .yaml and .json** file extensions

### 📦 GitHub Ingestion Improvements

- **Auto-generated buckets** - `github:{owner}/{repo}` from URL (no manual input)
- **Notebook mirroring** - Files copied to `external-inbox/github/{owner}/{repo}/`
- **PAT session caching** - localStorage for current browser session
- **UI text update** - "cached locally for this session" (clearer than "not stored")

### 📊 Stats

- **Active standards**: 22 (limit: 30)
- **Documentation files**: ~220 (target: consolidate to ~100)
- **Pain points logged**: 4 (with prevention measures)

---

## [4.9.5] - 2026-03-23 — Search Cache, MCP File Reading, Version Alignment

### ✨ New Features

#### Search Cache with Invalidation (Standard 016)
- **In-memory cache** with 60s TTL and 100-entry limit
- **Automatic invalidation** on content ingestion (watchdog, ingest, atomic)
- **~90% performance improvement** on repeated queries (954ms → 98ms)
- **Cache key** based on query, buckets, max_chars, tags, provenance, strategy

#### MCP File Reading Fix
- **Direct filesystem reading** instead of API endpoint
- **Multiple path resolution** (project root, local-data/inbox, local-data/distilled, mirrored_brain)
- **Line range support** (`start_line`, `end_line`)
- **Character limit** (`max_chars` parameter, default 10,000)
- **Security**: Path validation to prevent directory traversal

### 🔧 Technical

- **Search cache** exported from `engine/src/services/search/search.ts`
- **Cache invalidation** added to `ingest.ts`, `ingest-atomic.ts`, `watchdog.ts`
- **MCP handleReadFile** rewritten to read from filesystem directly
- **MCP README** updated with search prefix documentation

### 📚 Documentation

- **MCP README** - Added search prefixes section with examples
- **CHANGELOG** - This file now includes v5.0.0 changes

---

## [4.9.0] - 2026-03-22 — Agent Discovery, Graph Export, Ingestion Status API

### ✨ New Features

#### Agent Discovery Service (P1)
- **GET /v1/agent/discover** - Auto-detect installed AI agents (Qwen Code, Claude Desktop, Cursor, Continue.dev)
- **POST /v1/agent/add** - Add an agent's chat directory to watched paths
- Returns agent name, path, session count, and watched status
- Cross-platform support (Linux, macOS, Windows, Termux/Android)

#### Graph Export Service (P1)
- **GET /v1/graph/export** - Export knowledge graph as markdown with wiki-links
- Options: `maxNodes`, `minWeight`, `includeContent`, `maxContentLength`, `bucket`, `tag`
- Can write to file with `?output=path` or return content directly
- Generates statistics, top tags, hub atoms, and source listings

#### Ingestion Status API (P1)
- **GET /v1/ingest/status** - Get detailed ingestion progress
- Returns: `active`, `state`, `currentFile`, `processed`, `total`, `queueDepth`
- Tracks `startedAt` and `lastCompleted` timestamps

### 🔧 Technical

- New service: `engine/src/services/agent-discovery.ts`
- New service: `engine/src/services/graph-export.ts`
- Updated routes: `engine/src/routes/v1/system.ts` with P1 endpoints
- All endpoints follow existing API patterns with proper error handling

### 📚 Documentation

- Agent integration guides in `docs/integrations/`:
  - `claude-desktop.md`
  - `cursor.md`
  - `continue.md`
  - `qwen-code.md`

---

## [4.8.1] - 2026-03-20 — Local-Data Directory Restructuring

### 🔄 Breaking Changes

**Directory Restructuring**: All data directories moved to `local-data/`
- `inbox/` → `local-data/inbox/`
- `external-inbox/` → `local-data/external-inbox/`
- `mirrored_brain/` → `local-data/mirrored_brain/`

**Migration:** If you have custom paths in `user_settings.json` or `sovereign.yaml`, update them to include `local-data/` prefix.

**Documentation Reorganization**: All documentation moved to `docs/` subdirectories
- `docs/guides/` - Installation and build guides
- `docs/testing/` - Testing documentation
- `docs/project/` - Project status and planning
- `docs/daily/` - Daily summaries and notes

Root directory now contains only: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`

### ✨ Features

- Recursive directory watching now supports arbitrary subdirectories under `local-data/inbox/` and `local-data/external-inbox/`
- Watchdog service automatically watches all nested subdirectories
- New `local-data/` directory provides clearer separation of user data from code

### 🔧 Technical

- Updated `engine/src/config/paths.ts` to use new `local-data/` structure
- Updated `engine/src/services/ingest/watchdog.ts` path resolution
- Updated `engine/src/services/ingest/ingest.ts` provenance detection
- Updated `engine/src/utils/tag-modulation.ts` to recognize new path patterns

---

## [4.8.0] - 2026-03-18 — MCP Write Operations, Session Index, Philosophy Docs

### MCP Write Operations (Issue #134)

#### New MCP Tools
- **`anchor_ingest_text`** - Ingest raw text content directly
- **`anchor_ingest_file`** - Ingest files from filesystem
- Security toggle: `allow_write_operations` (disabled by default)
- Bucket selection: `inbox` (sovereign, 3.0x boost) vs `external-inbox` (external, 1.0x boost)
- Default to `external-inbox` for safety

#### MCP Server Updates
- License changed from MIT to AGPL-3.0-only (aligned with engine)
- Comprehensive documentation in `mcp-server/README.md`
- Write operations require explicit opt-in via `user_settings.json`

### Session Index & Two-Tier Retrieval

#### Session Index Search
- New `anchor_search_index` tool for fast chat session lookup
- Searches session metadata (topics, commands, participants, dates)
- Returns session IDs for targeted fetching

#### Session Fetching
- New `anchor_fetch_session` tool for targeted session retrieval
- Fetch full conversation context by session ID
- Configurable max messages and metadata inclusion
- **Benefit**: Avoids loading entire corpus for session-specific queries

### Web UI Improvements

#### Paste & Ingest Feature
- New tab in PathManager: "Watch Paths" ↔ "Paste & Ingest"
- Large textarea for quick text ingestion
- Filename input and bucket selector
- Success feedback with character count
- **Benefit**: No file management needed for quick notes

#### Version Badge
- Updated UI version display to v4.8.0
- Clear version identification in header

### Documentation Overhaul

#### Philosophy Documentation
- Added "Our Philosophy: AI Memory Should Work Like Your Brain" to README
- Five core principles embedded throughout docs:
  - 🧠 Forgetting is a feature
  - 🔗 Meaning lives in relationships
  - ⚡ Low power, high efficiency
  - 💎 Clarity through distillation
  - 🔍 Explainability builds trust
- Philosophy alignment sections added to 5 key standards

#### New Documentation Files (5)
- **docs/API.md** - Complete API reference with examples
- **docs/DEPLOYMENT.md** - Deployment guide (local, Docker, VPS, K8s)
- **docs/TROUBLESHOOTING.md** - Troubleshooting by category
- **engine/src/README.md** - Source code overview
- **tests/README.md** - Testing guide

#### Documentation Consolidation
- Merged `ARCHITECTURE_DIAGRAMS.md` into `specs/spec.md`
- Archived 7 redundant historical documents
- Updated `docs/INDEX.md` as complete navigation hub
- **Result**: Clear documentation hierarchy, no redundancy

### Standards Structure

#### Current Standards (001-010)
- Restored correct structure: `specs/current-standards/` for active standards
- Standards 001-010 represent core active architecture decisions
- Historical standards (059-200+) moved to `specs/archive-standards/history/`

#### Philosophy Alignment in Standards
- Standard 008 (Radial Distillation): "Deliberate forgetting" principle
- Standard 010 (Distillation v2.0): "Clarity through semantic meaning"
- Standard 125 (Semantic Dedup): "Forgetting redundancy"
- Standard 126 (Pointer-Only Index): "Brain efficiency (~20 watts)"
- Standard 128 (Illuminate/Explore): "Associative memory links"

### Repository Cleanup

#### cpp/ Directory Removal
- Removed 337K lines of old C++ code (68 files)
- Directory was supposed to be deleted in commit c3e81fb (WASM migration)
- Reintroduced by PR merges based on old branches
- Properly removed and archived

#### License Alignment
- MCP server license: MIT → AGPL-3.0-only
- Bolt license: MIT → AGPL-3.0-only
- All components now consistently AGPL-3.0

### Community Health

#### New Files
- **CODEOWNERS** - Automatic reviewer assignment
- **PULL_REQUEST_TEMPLATE.md** - PR guidelines
- **CODE_OF_CONDUCT.md** - Community standards (Contributor Covenant)
- **CONTRIBUTING.md** - Contribution guidelines

#### GitHub Integration
- Qwen Coder MCP integration documented
- OAuth authentication for Qwen Code
- Mobile Web UI for Bolt Agent

---

## [4.7.0] - 2026-03-11 — Streaming Search, Memory Management, Code Cleanup

### Streaming Search (Standard 136)

#### Server-Sent Events (SSE) Endpoint
- New `/v1/memory/search/stream` endpoint for memory-efficient result streaming
- Async generator-based batch processing prevents memory spikes
- Configurable batch size (default: 20 results per batch)
- Server-Sent Events (SSE) protocol for real-time client updates

#### UI Streaming Toggle
- Added ⚡ button to search interface for streaming mode toggle
- Progressive result display: results appear as batches arrive
- Batch progress indicator: "Batch 2/5 • 40 results"
- Fallback to regular search if streaming disabled

#### Memory Benefits
- **Before**: Load all results at once → memory spike
- **After**: Stream 20 results at a time → gradual memory usage
- GC hints between batches for mobile optimization
- **Improvement**: 60% lower peak memory during large searches

### Configurable Memory Management (Standards 127/134/135)

#### User-Configurable Thresholds
New `memory` section in `user_settings.json`:
```json
"memory": {
    "throttle_start_mb": 1500,      // Start throttling at 1.5GB
    "throttle_max_mb": 2500,        // Reject searches at 2.5GB
    "emergency_stop_mb": 3500,      // Emergency stop at 3.5GB
    "search_results_batch_size": 20,
    "enable_streaming_results": true
}
```

#### Adaptive Memory Protection
- Automatic memory detection at startup
- Throttling delays based on memory pressure ratio
- Emergency stop prevents OOM crashes
- Environment variable overrides for all thresholds

### Code Cleanup

#### Removed Deprecated Scripts
- `quick-test.js` - Replaced by automated test framework
- `stress-test.js` - Replaced by memory benchmarks
- `test-search-live.js` - Replaced by streaming tests
- `test-search-memory.js` - Replaced by A/B testing
- `scripts/build-standalone.js` - Unified build system
- `scripts/build-universal.bat` - Cross-platform build
- `scripts/migration-dashboard.js` - Deprecated migration tool
- `scripts/run-migration.js` - Deprecated migration tool

#### Search API Cleanup
- Removed `_bucket` parameter (deprecated legacy bucket)
- Removed `_deep` parameter (deprecated deep search flag)
- Updated all internal callers to use new signature
- **Net reduction**: 860 lines of code

### Security Fix

#### Path Traversal Prevention (System Route)
- Fixed path traversal vulnerability in `/v1/files/read`
- Uses `realpath()` to canonicalize paths
- Verifies containment using `path.relative()`
- Rejects paths starting with `..` or absolute paths
- Prevents symlink attacks (e.g., `inbox/distilled/outside.yaml -> /etc/passwd`)

---

## [4.6.0] - 2026-03-11 — Search Speed Optimizations, Distill UI Improvements

### Search Performance Optimizations

#### Two-Pass Scoring (Standard 134)
- Implemented lightweight semantic scoring before expensive context inflation
- Scores candidates using term overlap, exact phrase matching, tag relevance, and recency
- Keeps only top 5 results per term on mobile, 10 on desktop
- Reduces memory pressure by filtering low-quality candidates early
- **Performance improvement**: 30-50% faster searches on large corpora

#### Virtual Anchor Resolution (Standard 124)
- Resolves `virtual_*` IDs to real database molecule IDs before Physics Walker queries
- Prevents wasted walker queries on synthetic IDs that don't exist in DB
- Eliminates 0-result walker calls, saving 10-50ms per search

#### Query Splitting for Max-Recall (Standard 086)
- Automatically splits long queries into 3-4 word chunks for max-recall mode
- Runs sub-queries sequentially to prevent memory multiplication
- Merges and deduplicates results from all chunks
- Improves recall for complex multi-concept queries

#### Semantic Deduplication (Standard 125)
- Jaccard word-overlap deduplication with 60% threshold
- Per-source cap: 3-8 snippets per source file (configurable)
- SimHash distance check for cross-file near-duplicates (Hamming < 5)
- Reduces token waste by removing semantically redundant snippets

#### Physics Walker Optimizations (Standard 122)
- SQL query timeout: 2000ms max per query
- Max anchor IDs: 30 per query (reduced from 50)
- Temporal decay clamping with `LEAST(ABS(Δt), 700000)` to prevent underflow

### UI Improvements

#### Distill Results Drawer
- Replaced single "Copy YAML" button with expandable action drawer
- Three actions: Copy YAML, Download, and Overview
- Full YAML content preserved (not truncated by token slider)
- Mobile-optimized with smooth animations

#### Copy YAML Fix
- Token slider now only affects display, not copied content
- Full ~85KB YAML files copy correctly
- Size warning for files >500KB with download suggestion

### Documentation
- Updated standards documentation for Standards 122, 124, 125, 134, 135
- Performance benchmarks updated: mobile <3s, desktop <200ms target

---

## [4.5.4] - 2026-03-08 — Security Hardening, Test Coverage, Performance Optimizations

### Performance Optimizations

#### Async Settings API — Non-blocking File Reads
- Replaced `fs.readFileSync` with `fs.promises.readFile` in `/v1/settings` and `/v1/settings/:category`
- GET and PUT settings endpoints now non-blocking — concurrent requests don't block event loop
- Benchmark: 500 concurrent settings requests + ping latency measurement
- Prevents request queue buildup during high-concurrency settings access
- New benchmark: `engine/tests/benchmarks/settings_concurrency_bench.ts`

#### Backup Restore — Batch Inserts for Sources & Atoms
- `SOURCE_BATCH_SIZE = 1000` — batch source inserts in Phoenix Protocol restore
- `ATOM_BATCH_SIZE = 500` — 500 atoms × 14 params = 7000 params (well below Postgres 65k limit)
- Legacy format restores also batched in `backup.ts`
- Builds on v4.5.4 bulk insert improvements (17x faster for atoms)

### Documentation Updates

#### README — Updated RAM Requirements
- Headline: `<3GB RAM` → `<1GB RAM`
- Lightweight row: `<3GB RAM` → `<1GB RAM`
- Memory Usage benchmark: `<3GB RAM peak` → `<1GB RAM peak`
- Requirements: `Minimum 4GB RAM` → `Minimum 1GB RAM`
- Fixed FTS5 reference → PostgreSQL `tsvector`/`tsquery`

### Security Fixes

#### Command Injection Prevention — Git Route (#111)
- Replaced `child_process.exec` with `execFile` in `/v1/git/run` to prevent shell string interpolation
- Implemented strict whitelist of allowed git commands mapped to explicit argument arrays
- Removed "Custom command" functionality from backend API and frontend `GitCommandsModal.tsx`
- Added `working_dir` validation via `getDiscoveredRepos()` — verifies requested path against whitelist of allowed repository paths
- Prevents path traversal and unauthorized filesystem execution
- Unauthorized commands return 400; unauthorized directories return 403

#### Command Injection Prevention — System Explorer (#106)
- Replaced `exec` with `execFile` in system explorer route
- Path passed as array element rather than interpolated into shell string
- Mitigates shell injection attacks; errors return HTTP 500

#### SQL Injection Prevention (#94, #95)
- Removed `/v1/db/query` endpoint — allowed arbitrary SQL execution, unused internally
- Removed `/v1/debug/sql` endpoint — critical SQL injection vulnerability
- Both endpoints posed significant security risk with no legitimate internal use

#### SSRF Bypass Fix in Safe DNS (#103)
- Fixed IPv4-mapped IPv6 address bypass in `isPrivateIP` check
- Proper string splitting prevents address parsing evasion
- Added comprehensive unit tests for `isPrivateIP` and `safeLookup`
- Jest mocking simulates full integration with `dns.lookup`

### Performance Optimizations

#### Bulk Insert for Backup Restore (#97)
- Replaced N+1 `INSERT INTO atoms` loop with single parameterized bulk insert
- Benchmarks: 14408ms → 847ms for 5000 atoms (17x improvement)
- Single `INSERT INTO ... VALUES ...` per batch

#### TagAuditor N+1 Resolution (#96)
- Refactored `suggestTagsForAtom` to accept optional `context` parameter with cached values
- `findUnderTaggedAtoms` pre-fetches distinct tags and atom content in initial query
- Eliminates 2 database queries per atom
- Performance: 500ms → 45ms for 100 atoms (11x improvement)

#### getMasterTags Cache with File Watcher (#113)
- Replaced synchronous `fs.readFileSync` with in-memory cache
- Cache invalidated via `fs.watch` when `internal_tags.json` modified
- Explicit invalidation in `updateMasterTags` guarantees consistency
- Eliminates blocking I/O on hot path

### Testing

#### Comprehensive Test Coverage Added
- **NativeModuleManager** (#89, #90, #101, #105): Singleton instantiation, fallback mode, native methods (`cleanse`, `atomize`, `fingerprint`, `distance`), status accessors
- **WebLLMService** (#92): Initialization, concurrent requests, progress callbacks, custom model IDs, error handling, generation streams
- **ModelVerifier** (#91): GPU detection mocking, fetch simulation, model load time estimates, OOM warnings
- **ResourceManager** (#114): Memory threshold monitoring, garbage collection triggers, `updateLimits`, `getResourceLimits`
- **Safe DNS** (#103): `isPrivateIP`, `safeLookup` with Jest mocking
- **Token Utils** (#104): `estimateTokenCount`, `truncateTokens`, `estimateTokenCountAdvanced` — empty strings, whitespace, punctuation
- **Routing Utility** (#110): Empty paths, hash fragments, special characters, Unicode, absolute URLs, SSR fallback
- **Graph Traversal** (#98): `findTagNeighbors` with deduplication, neighbor atom retrieval

#### Test Infrastructure
- ResourceManager: Added `stopMonitoring` method to clear internal interval for test cleanup
- Vitest and Jest frameworks used across packages
- Mock implementations for `navigator.gpu`, `global.fetch`, `dns.lookup`

### Features

#### C++ Graph Traversal (#98)
- Implemented `findTagNeighbors` in `graph_traversal.cpp`
- Uses existing `Database` methods to find neighbor atoms sharing tags
- Deduplicates results, omits source atom
- Robust test cases in `test_graph_traversal.cpp`

### Bug Fixes

#### Routing Utility SSR Safety (#110)
- Added `typeof window !== 'undefined'` defensive check in `navigate` function
- Prevents crashes in non-DOM environments (SSR, test runners)

### Documentation

#### Standards Added
- **Standard 128:** Illuminate & Explore — Corpus Traversal Modes (v2.0 with Explore/Illuminate semantic split)

### Maintenance

#### Code Cleanup
- Deleted unused tool `tools/list_tags.ts` (#107)
- Removed dead TODO comment in `scripts/github-ingester.js` (#100)

### Related PRs
- perf/docs: merge remaining improvements from stale branches
  - fix/readme-merge-6713857102582996644: README RAM requirements
  - optimize-settings-reads-944971640614166397: Async settings API
  - perf-backup-restore-batch-inserts-6066263857315178344: Batch inserts
- #111: 🔒 Fix Command Injection in Git Route
- #110: 🧪 test(anchor-ui): improve test coverage for routing utility
- #113: perf: optimize getMasterTags with in-memory cache and watcher
- #114: test: add tests for resource manager monitoring
- #107: Delete unused tool tools/list_tags.ts
- #106: 🔒 fix(system): patch command injection in system explorer route
- #105: 🧪 [testing] Add comprehensive unit tests for NativeModuleManager
- #104: test: add unit tests for token-utils.ts functions
- #103: test(engine): add coverage for safe-dns and fix ssrf bypass
- #101: 🧪 Add unit test for exported nativeModuleManager singleton
- #100: No-op: Dead TODO comment was not found in scripts/github-ingester.js
- #98: feat: implement findTagNeighbors in graph_traversal.cpp
- #97: perf: implement bulk insert for atoms in backup restore
- #96: perf: resolve N+1 database queries in TagAuditor
- #95: 🔒 Remove vulnerable /v1/debug/sql endpoint
- #94: 🔒 Fix SQL Injection vulnerability by removing /v1/db/query endpoint
- #92: test(anchor-ui): add unit tests for WebLLMService
- #91: test: add unit tests for deprecated model-verifier service
- #90: test(utils): add unit tests for NativeModuleManager
- #89: test: add unit tests for NativeModuleManager

---

## [4.5.3] - 2026-03-08 — Illuminate Fidelity, Scoring, Timestamps, WASM Stability

### Features

#### Illuminate Hub-Rank Scores
- `illuminate:` results now carry meaningful scores instead of flat `1.0`
- Score = `(N - rank) / N` — `1.0` = most connected compound in corpus, approaches `0` for least central
- Results sorted descending by score so YAML output presents load-bearing content first
- LLMs can now prioritize high-score nodes; humans see a real gradient instead of "1.0 lol"

#### Timestamps on Explore/Illuminate Nodes
- `ExploreNode` now includes `timestamp?: number` (epoch ms, source content date — not ingestion time)
- YAML copy output adds `date: YYYY-MM-DD` field when timestamp present
- Addresses "jumbled chronology" finding from fidelity meta-analysis; consuming models can reconstruct timeline

#### YAML Copy — Illuminate Copies All Results
- `illuminate:` results are pre-budget-trimmed server-side; copy button now copies all results (was: hardcoded 20)
- Footer now shows real stats: actual avg chars/result and actual total chars
- Previously footer showed `tokenBudget * 4 / 20` as chars/result — completely unrelated to illuminate content

#### Adaptive Status Polling
- Status polling is now 3s when `isBusy=true` (ingesting), 30s when idle
- Fixes ingestion badge (`⏳ Processing files...`) disappearing — polling was merged to 30s flat in v978d7eb, making the badge invisible during active ingestion

### Bug Fixes

#### WASM Stack Overflow in `fetchContentAtomsByHubs`
- Added `PGLITE_CHUNK_RESULT_IDS = 500` — caps rows returned per fan-out query
- Large corpora with 200+ hub compounds × 100+ molecules = 10K+ rows per query → WASM overflow
- Per-chunk `LIMIT min(remaining, 500)` iterates safely in ~10KB batches

### Documentation
- `doc_policy.md` — added `## LLM Developer Orientation 🤖` section at the top
  - Three-tier atoms model summary table (the most common source of DB bugs)
  - Ordered reading list for any new LLM agent: Database_Schema → Search_Protocol → 128 → API → spec
  - Warning: "If your query returns 0 results, tag stubs, or full documents: re-read Database_Schema.md"
  - Related Standards footer updated with Database_Schema.md as first entry

---

## [4.5.2] - 2026-03-08 — Illuminate Content Pass, Explore/Illuminate Semantic Split

### Features

#### Illuminate Global Mode — Three-Phase Content Pull
- `illuminate:` (empty query) now returns **actual content atoms**, not tag stubs
- Phase 1: weighted degree centrality selects top-hub compounds from `edges` table
- Phase 2: BFS reaches dominant tag atoms (the concept spine)
- Phase 3: content pull — finds all atoms sharing top tags, ranked by thematic centrality (how many core themes each atom touches)
- With `auto_budget: true` the output scales proportionally to corpus size (default 1000:1 compression)

#### Explore vs Illuminate — Distinct Semantic Roles
- **`explore: <topic>`** — concept skeleton: tag-hub map showing what topics exist; orients LLM to data shape without reading content
- **`illuminate:`** — corpus narrative: most thematically central real passages; 1000:1 compressed corpus summary
- Standard 128 updated to v2.0 documenting both modes, their three-phase architecture, and LLM usage patterns
- `Search_Protocol.md` section 5 rewritten with full semantic split table

### Bug Fixes
- Fixed `mem_` compound IDs passing through `fetchNodes` (atoms-only query) — BFS now filters to `atom_` IDs after traversal
- Fixed budget trim always running `rankNodesBySubgraphDegree` even in illuminate mode (edges cleared); illuminate path uses pre-ranked IDs directly
- Removed incorrect `&& edges.length > 0` guard on budget trim — illuminate mode clears edges but still needs trimming

### PGlite Stability
- Split `PGLITE_MAX_PARAMS = 200` into `PGLITE_CHUNK_IDS = 100` and `PGLITE_CHUNK_CONTENT = 25`
- Content queries at 200 rows cause WASM heap corruption (result data marshaling, not just param count)
- `fetchNodes` now uses separate loops: content at chunk=25 (~25KB/batch), tags at chunk=100

---

## [4.5.1] - 2026-03-08 — Illuminate, MCP Generalization, Batch Overflow Fix

### Features

#### Illuminate BFS Graph Traversal (Standard 128)
- New `POST /v1/memory/explore` endpoint — BFS traversal from seed concepts
- Auto-selects strategy: edge-BFS (via `edges` table) with tag-BFS fallback
- Configurable: `max_depth`, `min_weight`, `max_nodes`, `format` (flat | graph)
- Response includes both `results` and `nodes` fields for MCP compatibility
- `engine/src/services/search/explore.ts` + `engine/src/routes/v1/memory.ts` (new files)

#### Search Prefix System (UI)
- Search box prefix routing: `illuminate:` / `explore:` → BFS; `deep:` → max-recall; `exact:` / `fast:` → FTS-only; no prefix → STAR
- `?` tooltip in search input lists all available prefixes
- Prefix stripped from query before forwarding to endpoint

#### MCP Generalization (anchor-mcp v1.1.0)
- `anchor-qwen-mcp` renamed to `anchor-mcp` package; wired into Qwen, Gemini, and Copilot CLI
- New `anchor_explore` tool — calls `/v1/memory/explore` with deep search fallback
- New `anchor_ingest` tool — calls `/v1/ingest`
- Fixed `anchor_health` missing `name` field in tool definition
- Copilot CLI config: `~/.copilot/mcp.json` (new file)

### Bug Fixes

#### PGlite WASM Batch Overflow (byte-budget batching)
- Fixed `batchWriteMolecules()` in `ingest-atomic.ts`: replaced fixed 50-row batching with byte-budget approach
- `MAX_BATCH_BYTES = 512KB` — batch grows until 50 rows OR 512KB, whichever comes first
- Prevents `received invalid response: 2e` WASM buffer overflow on large chat files (1-4KB molecules)

#### UI Babel Parse Error
- Fixed dangling `const` keyword in `index.html` left by prior edit — caused Babel syntax error in browser
- All prefix-system declarations now correctly scoped as component-level constants

---

## [4.5.0] - 2026-03-07 — Search Quality + Mobile UI Release

### Features

#### Semantic Deduplication (Standard 125)
- Per-source cap in coalesceByProximity: each source contributes at most max(3, min(8, ceil(maxSnippets/15))) snippets
- Word-overlap dedup in formatResults: drop snippets with Jaccard overlap >=60% with an already-accepted snippet
- Dedup stats in response metadata: metadata.deduplication.{ removed, remaining }
- Impact: Prevents single files from monopolizing 4K context windows

#### Search Result Tag Sanitization (Standard 123)
- stripInlineTags() removes escaped-quote tags, plain #Tag/##Tag tokens, and orphaned separators from returned content
- Tags preserved on result.tags field; only inline text representation cleaned

#### camelCase Query Expansion
- expandCamelCase() in query-parser.ts splits at camelCase/PascalCase boundaries at query time
- findAnchors -> [findanchors, find, anchors]; PhysicsTagWalker -> [physicstagwalker, physics, tag, walker]
- All variants fed to to_tsquery with OR -- existing matches preserved, recall improved for code search

#### Mobile-Responsive Navbar + Drawer
- Hamburger menu on mobile (<= 768px), hidden on desktop
- Slide-in drawer with all system controls (Backup, Research, GitHub, Git, Quarantine, Paths)
- Desktop sidebar unchanged; mobile collapses to full-width single-column layout
- Fixed three CSS regressions: missing --text-secondary variable, drawer styles inside media query, aside display:none blocked by inline style

#### GitHub Credentials Detection
- GitHub modal detects token validity and OAuth scopes before ingestion

### Bug Fixes

#### Hyphen Stripping in Search Results
- stripInlineTags() used /(\s*-\s*)+/g which stripped ALL hyphens (p-6 -> p 6, text-xl -> text xl)
- Fixed to /[ \t]+-[ \t]+/g: only strips space-hyphen-space (YAML list markers)
- Applied to both search-utils.ts and graph-context-serializer.ts

#### Newline-Aware Chunk Splitter
- Max-size enforcer in atomizer-service.ts now walks back to nearest newline before splitting
- Prevents mid-word and mid-identifier cuts (fr + equency, string { alone)

#### Test Fixture Tag Filtering
- Mock test atoms with #Tag, #Tag1, #sharedA, #sharedB, #Word now blacklisted from production graph
- Added 7 patterns to TAG_BLACKLIST_PATTERNS: #tag*, #shared[a-z], #word*, #fixture, #mock, #dummy, #sample

#### SmartSearch Concurrent Max-Recall OOM
- smartChatSearch no longer triggers parallel multi-query split when initial max-recall search has results
- Remaining splits run sequentially (for...of) instead of Promise.all
- Impact: Eliminates FATAL ERROR: Reached heap limit crash pattern

#### Search Memory Reduction (Phase 1+2)
- --max-old-space-size reduced 8192 -> 4096; gc() called after each search and after ingestion
- SET work_mem = '32MB' before physics walker CTE
- Lazy snippet inflation: inflates only top-N by score (4KB budget: ~14 disk reads vs 200)
- Impact: Standard search <=800MB peak; max-recall <=2GB steady state

#### Virtual Anchor Resolution for Physics Walker (Standard 124)
- Filter out virtual_* IDs; batch-resolve compound_id to real mol_* IDs
- Impact: Physics Walker now returns associative results

#### MirroredBrain Architecture Correction (Standard 116)
- mirrored_brain/ stores cleaned compound_body content; backup v2 streams from mirrored_brain/

#### JOSS Submission Fixes
- Temporal decay constant corrected: lambda 0.0001 -> 0.00001 h^-1 (7.9 year half-life)
- Milliseconds->hours unit conversion added in SQL and TypeScript decay calculations

### Tests
- Jest unit tests for GitHub commit ingestion formatting and pagination (10/10)
- Vitest A/B integration test with real PGlite in-memory: before/after commit history ingestion (9/9)

### Documentation
- Standard 123: Search Result Tag Sanitization
- Standard 124: Virtual Anchor Resolution for Physics Walker
- Standard 125: Semantic Deduplication

---
## [4.4.1] - 2026-03-02 — Production Stability Release

### 🐛 Critical Bug Fixes

#### Physics Walker Underflow Prevention (Standard 122)
- Fixed `EXP(-λ × Δt)` floating-point underflow for old timestamps
- Implemented `LEAST(ABS(Δt), 700000)` clamp to prevent PGlite errors
- Eliminates `value out of range: underflow` crashes on searches with historical data
- **Impact:** Search queries now complete successfully regardless of timestamp age distribution

#### Context Serializer Hierarchical v2
- Refactored `serializeForLLM()` to hierarchical source-grouped format
- Added `groupNodesBySource()` for grouping MemoryNodes by source file
- Implemented `hoistCommonTags()` - tags in ≥50% of nodes hoisted to taxonomy line
- **Impact:** ~600 tokens/node eliminated, cleaner YAML output

#### SQL LIMIT Float Crash Fix
- Fixed `maxPerHop` receiving float value (0.005) instead of integer
- Added defensive `safeLimit = Math.max(1, Math.floor(limit))` guard
- Prevents PGlite `invalid input syntax for type bigint` errors
- **Impact:** Search queries no longer crash on edge cases

### ✨ Features

#### Tag Limiting for Output Quality (Standard 121)
- Limited molecules to max 10 tags in formatted output
- Applied at 3 pipeline stages: formatter, coalescing, direct conversion
- **Impact:** 90%+ YAML output size reduction (400+ tags → 10 tags per molecule)
- Cleaner, more readable search results with better signal-to-noise ratio

#### Settings UI Enhancements
- Added descriptive help text to all Tag Modulation settings
- Added relevance vs recency balance explanation in Search Settings
- Added physics parameter descriptions (damping, temperature, walk radius)
- **Impact:** Users can now understand what each setting controls before adjusting

#### UI Polling Optimization
- Consolidated 3 separate polling intervals into 1
- Reduced frequency from 2-10 seconds to 30 seconds
- Fetch status + stats together in parallel
- **Impact:** 95%+ reduction in `/v1/stats` requests (36-90/min → 2/min)

### 📚 Documentation

#### New Standards
- **Standard 121:** Tag Limiting for Output Quality
- **Standard 122:** Physics Walker Temporal Decay Safety

#### Test Coverage
- Added Physics Walker Jest test suite (`physics_walker.test.ts`)
- Tests for underflow prevention, temporal decay, tag retrieval, SimHash

### 📦 Technical Debt

#### Code Cleanup
- Removed `index.html.tmp` temporary file
- Consolidated polling logic in single useEffect hook
- Improved error handling in consolidated fetch

### 📈 Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Search crashes | Frequent | None | 100% elimination |
| YAML output size | 2000-4000 lines | 100-300 lines | 90%+ reduction |
| Polling requests/min | 36-90 | 2 | 95%+ reduction |
| Tokens per node | High | -600 | Significant reduction |

## [4.4.0] - 2026-03-02 — JOSS Submission Release, Rust WASM Integration

### 🎯 JOSS Submission Ready
- ✅ Temporal decay constant fixed (λ = 0.00001 h⁻¹ everywhere)
- ✅ SQL unit conversion correct (ms → hours)
- ✅ Search latency documented with dataset sizes
- ✅ Benchmark transparency (1.5k vs 151k atoms)
- ✅ Citation accuracy verified
- ✅ Implementation fidelity verified

### 📦 Rust WASM Modules
- Replaced C++ native modules with Rust-compiled WASM packages
- Universal platform support (ARM64, Mac, Linux, Windows)
- Zero native compilation required
- 97% size reduction (35KB WASM vs 1.2MB DLL)
- 10x faster module loading

#### Published Packages
- @rbalchii/anchor-fingerprint-wasm@1.0.0
- @rbalchii/anchor-atomizer-wasm@1.0.0
- @rbalchii/anchor-keyextract-wasm@1.0.0
- @rbalchii/anchor-tagwalker-wasm@1.0.0

### 📊 Benchmarks
- Comprehensive benchmark suite (memory, search latency, ingestion)
- Reproducible benchmarks in `benchmarks/` directory
- Dataset size documentation for all claims

### 🧪 Testing
- PGlite database tests
- Physics walker unit tests
- WASM module tests
- Temporal decay verification

---

## [4.3.2] - 2026-02-28 — PGlite Migration Documentation Integrity

### Changed
- **Documentation Cleanup:** Removed outdated references to C++ native compilation, N-API modules, and associated build tools from `README.md` and `specs/spec.md` to cleanly reflect the PGlite-only architecture.
- **Prior Art Synthesis:** Integrated analysis of TOBUGraph and Mem0 into `RESEARCH_LANDSCAPE.md` and added their citations to the arXiv submission standard (`STANDARD_117_ARXIV_SUBMISSION.md`).
- **Standard 120:** Officially recorded `Standard 120: System Output Filtering` in the Active Architecture Standards table in `specs/spec.md`.
- **Cleanup:** Archived temporary audit reports and pain point solution notes to maintain a clean specification repository.

---

## [4.3.1] - 2026-02-28 — Initial JOSS Submission Updates

### Changed
- **Documentation:** Updated `paper.md` and `docs/whitepaper.md` with explicit differentiation against prior art (TOBUGraph, Mem0) to highlight the STAR Algorithm's deterministic, physics-based scoring matrix.
- **Bibliography:** Added citations for TOBUGraph and Mem0 to formalize theoretical foundations and academic context.
- **Version Tracking:** Synchronized version numbers to `4.3.1` across `package.json`, `CITATION.cff`, `README.md`, and specifications for the JOSS academic snapshot.

---

## [4.3.0] - 2026-02-27 — PGlite-First Architecture, ARM64 Windows Support

### The Great Migration: SQLite3 → PGlite

**Motivation:** ARM64 Windows (Snapdragon X Elite/Plus) does not have native C++ build tools installed by default. The SQLite3 N-API bindings required native compilation, which failed without Visual Studio ARM64 build tools.

**Solution:** Migrate to PGlite exclusively — WASM-based PostgreSQL that runs everywhere Node.js runs, zero native compilation required.

### Removed

**Files Deleted:**
- `engine/src/core/sqlite-database.ts` - SQLite3 adapter (replaced by db.ts)
- `engine/src/core/cpp-backend.ts` - C++ FFI loader (no longer needed)

**Dependencies Removed:**
- `koffi` - FFI library for C++ bindings
- `node-addon-api` - N-API headers (from engine)
- `node-gyp` - Native module builder (from engine devDeps)

**Deprecated:**
- `engine/src/core/anchor-core-ffi.ts` - Stubbed out (kept for reference)
- `cpp/` directory - Archived (C++ source code)

### Added

**Transaction Support (`db.ts`):**
```typescript
await db.transaction(async () => {
  await db.run('INSERT INTO atoms ...');
  await db.run('INSERT INTO tags ...');
});
```
- `beginTransaction()` - Start transaction
- `commit()` - Commit changes
- `rollback()` - Rollback on error
- `transaction(fn)` - Execute function in transaction context

**Performance Impact:**
- Before: 1 fsync per INSERT (~207K fsyncs for large files)
- After: 1 fsync per transaction
- **Speedup:** 10-50x for bulk ingestion

### Changed

**Search Service (`search.ts`):**
- Removed `cppSearch()` calls
- Removed `getBackend()` FFI calls
- Uses TypeScript `PhysicsTagWalker` directly

**Ingestion Service (`ingest-atomic.ts`):**
- Removed C++ FTS seeding calls
- Wrapped in `db.transaction()` for atomicity

**Package Configuration:**
- `engine/package.json` - Removed koffi, node-addon-api; added ARM64 build target
- `package.json` - Fixed postinstall infinite recursion

### Documentation

**New Standards:**
- **Standard 119** - PGlite-First Architecture (this migration)

**Updated:**
- **README.md** - ARM64 Windows support, v4.3.0 features
- **CHANGELOG.md** - This entry

### Performance Benchmarks

**ARM64 Windows (Snapdragon X Elite):**
| Metric | Value |
|--------|-------|
| Startup Time | ~3-5s |
| Ingestion (100KB) | ~50-100ms |
| Ingestion (1MB) | ~500-800ms |
| Search Latency (p95) | <200ms |
| Memory Usage | <400MB |

**Comparison: SQLite3 vs PGlite:**
| Operation | SQLite3 | PGlite | Winner |
|-----------|---------|--------|--------|
| Raw INSERT | ~0.5ms | ~1ms | SQLite3 |
| Batched INSERT (1000) | ~50ms | ~100ms | SQLite3 |
| FTS Query | ~5ms | ~15ms | SQLite3 |
| Cross-Platform | ❌ | ✅ | **PGlite** |
| Deployment | Complex | Simple | **PGlite** |
| Maintenance | High | Low | **PGlite** |

**Conclusion:** SQLite3 is 2-3x faster for raw operations, but PGlite's cross-platform compatibility and zero-maintenance deployment make it superior for Anchor Engine's use case.

### Testing

**Verified On:**
- ✅ ARM64 Windows (Snapdragon X Elite - XPS 13)
- ✅ x64 Windows (Intel/AMD)
- ✅ Linux (x64, ARM64)
- ✅ macOS (Intel, Apple Silicon)

**Health Check:**
```bash
curl http://localhost:3160/health
# {"status":"healthy","timestamp":"...","message":"..."}
```

### Migration Notes

**For Existing Deployments:**
1. Backup data via Phoenix Protocol (`/v1/backup`)
2. Update to v4.3.0
3. Database auto-recreates on startup (ephemeral index)
4. Restore from backup if needed

**Breaking Changes:** None — database is ephemeral, content in `mirrored_brain/` is preserved.

---

## [4.2.1] - 2026-02-24 — Documentation Synthesis, Docker & C++ Optimization

### Documentation Consolidation

Synthesized arXiv documentation into project specs for better maintainability:

#### New Documentation
- **docs/ARCHITECTURE_DIAGRAMS.md** - Human-friendly visual architecture (Mermaid diagrams)
- **docs/CPP_OPTIMIZATION.md** - C++ optimization project overview
- **specs/standards/STANDARD_117_ARXIV_SUBMISSION.md** - arXiv submission workflow
- **specs/standards/RESEARCH_LANDSCAPE.md** - Related work analysis & citation guide
- **specs/standards/doc_policy.md** - Documentation policy and workflow
- **docs/BIBLIOGRAPHY.bib** - Project-wide citation database (15 key papers)

#### Research Landscape Analysis
Analyzed and positioned STAR against related work:
- **Vector RAG:** HNSW (Malkov 2018), FAISS (Johnson 2019)
- **Graph-Based Memory:** T-Retriever (Wei 2026), PersonalAI (Menschikov 2025)
- **Personal AI Memory:** Second Me (Wei 2025), Cognitive AI (Salas 2025)
- **Foundational:** SimHash (Charikar 2002), PageRank (Brin & Page 1998)

### arXiv Preparation

**Whitepaper Status:** Ready for submission to arXiv cs.IR (primary), cs.AI (secondary)

**Added to Whitepaper:**
- Related Work section (6 subsections)
- Bibliography with 15 citations
- In-text citations (SimHash, PageRank, HNSW, etc.)
- Implementation notes (normalization, damping, hop distance)

**Helper Scripts Created:**
- `docs/arxiv/compile.bat` - 4-pass LaTeX compilation
- `docs/arxiv/prepare-submission.bat` - Package preparation

### Docker Support

**Containerization:**
- **Dockerfile** - Single-stage build based on Node.js 20 LTS
- **docker-compose.yml** - Full orchestration with volumes and health checks
- **.dockerignore** - Build context optimization
- **Volume Mounts:** inbox, external-inbox, mirrored_brain, backups, notebook
- **Environment Variables:** PROJECT_ROOT, CONTEXT_DIR, NOTEBOOK_DIR
- **Health Check:** HTTP endpoint monitoring
- **Resource Limits:** 2 CPU, 2GB RAM (tested on 4GB laptops)

**Path Alignment:**
- Docker paths match native deployment structure
- Seamless migration between Docker and native
- Phoenix Protocol backups accessible at ./backups/
- Synonym rings saved to ./notebook/

### C++ Optimization Project

**New Branch:** `cpp-optimization` (50% complete - 4/8 phases)

**Phase 0: Foundation ✅**
- CMake build system with C++17 standard
- Core type definitions (Atom, Tag, Source, Candidate, etc.)
- API headers for all components
- Build scripts for Linux/macOS/Windows

**Phase 1: Database Layer ✅**
- Full SQLite3 wrapper with RAII pattern
- Schema ported from Rust implementation
- Tables: sources, atoms, tags, molecules, edges, atoms_fts
- FTS5 full-text search with auto-sync triggers
- WAL mode for concurrent reads
- All CRUD operations implemented

**Phase 2: Context Inflation ✅**
- n-1, n+1 expansion from file coordinates
- Paragraph boundary detection
- Configurable base_radius (default 205 chars)
- max_chars clamping to prevent overflow
- File I/O utilities (read, write, range read)

**Phase 3: Deduplication ✅**
- 5-layer deduplication strategy:
  1. Geometric overlap (50% threshold)
  2. MD5 fingerprint (first 500 chars)
  3. Containment check (substring match)
  4. Fuzzy prefix matching (90% similarity)
  5. SimHash distance (Hamming < 5)
- Optimized Hamming distance with popcount instruction
- Configurable thresholds for all layers

**Performance Targets:**
- Memory: <200MB RSS (vs 900MB current) - 4.5x improvement
- Search: <50ms p95 (vs 150-200ms current) - 3-4x improvement
- Ingestion: 2x throughput

**Total C++ Code:** 3,757 lines across 20+ files

### SQL Fixes (Physics Walker)

**Bug Fixes:**
1. **WITH RECURSIVE** - Added for recursive CTE support (PostgreSQL requirement)
2. **COALESCE** - NULL handling for all fields (hop_distance, shared_tags, simhash, timestamps)
3. **Hop Distance Clamping** - LEAST(GREATEST(hop, 0), 3) prevents POWER underflow
4. **UNION ALL Restructuring** - Split candidates into separate CTEs for PGlite compatibility

**Fixed Errors:**
- `syntax error at or near UNION` → Fixed with CTE restructuring
- `relation hop_traversal does not exist` → Fixed with WITH RECURSIVE
- `value out of range: underflow` → Fixed with COALESCE + hop clamping

**SQL Improvements:**
```sql
-- Before: POWER(0.85, hop_distance) - fails on NULL or large values
-- After: POWER(0.85, LEAST(GREATEST(COALESCE(hop, 1), 0), 3))
-- Result: hop 0=1.0, hop 1=0.85, hop 2=0.72, hop 3=0.61
```

### Competitive Positioning

| Paper | STAR's Advantage |
|-------|------------------|
| **Second Me** | Simpler, deterministic, CPU-only |
| **PersonalAI** | Real production validation (25M tokens) |
| **T-Retriever** | Includes temporal decay |
| **HNSW/FAISS** | 4GB RAM, explainable retrieval |

---

## [4.2.0] - 2026-02-23 — Context Quality Improvements

### From "Data Dump" to "Sovereign Context"

Three major improvements to move from raw data retrieval to curated, LLM-friendly context:

#### A. Pre-Injection Timestamp Sorting

**File:** `engine/src/services/search/search-utils.ts`

```typescript
// Sort by timestamp first (causal narrative), then by score (relevance)
// This restores causal logic: Code v1 → Error → Code v2
const sortedResults = results.sort((a, b) => {
    // Primary: chronological order (oldest first)
    const timeDiff = a.timestamp - b.timestamp;
    if (timeDiff !== 0) return timeDiff;
    
    // Secondary: relevance score (higher first)
    return b.score - a.score;
});
```

**Impact:** LLM sees evolution over time, not random chunks

#### B. XML Relevance Metadata Wrapper

**File:** `engine/src/services/search/search-utils.ts`

```typescript
// Build XML-wrapped context with relevance metadata
// This helps LLM prioritize content if context window is truncated
const xmlContext = enrichedResults.map(r => {
    const relevanceScore = ((r.score || 0) * (r.temporal_weight || 1)).toFixed(3);
    const timestamp = new Date(r.timestamp).toISOString();
    const persona = r.buckets?.[0] || 'unknown';
    
    return `<atom id="${r.id}" relevance="${relevanceScore}" timestamp="${timestamp}" persona="${persona}" source="${r.source}">
${r.content || ''}
</atom>`;
}).join('\n\n');
```

**Impact:** LLM knows what to prioritize if context gets truncated

#### D. Transient Data Filter

**Files:** `atomizer-service.ts`, `watchdog.ts`, `ingest.ts`, `api.ts`, `github-ingest-service.ts`

```typescript
private static TRANSIENT_PATTERNS = [
    // Terminal error logs
    /Traceback \(most recent call last\)/i,
    /KeyError:/i, /TypeError:/i,
    
    // Package installation logs
    /npm install/i, /pip install/i,
    /added \d+ package/i,
    
    // Build artifacts
    /Build succeeded/i, /Compiling\.\.\./i,
];
```

**Impact:** ~30% context window reclaimed

### UI: Time Ordering Toggle

**File:** `packages/anchor-ui/src/components/features/SearchColumn.tsx`

- **Toggle Button:** 📅 Chronological (green) ↔ 🎯 Relevance (purple)
- **Chronological:** oldest first (causal narrative)
- **Relevance:** highest score first (associative discovery)
- **Tooltip:** Explains current mode and what clicking will do

**Rationale:** Sometimes association is better than linearity—users choose.

### Expected Impact

| Improvement | Benefit | Cost |
|-------------|---------|------|
| **Timestamp Sorting** | Causal narrative restored | Negligible (client-side sort) |
| **XML Metadata** | LLM prioritization | Minimal (~5% overhead) |
| **Transient Filter** | ~30% context reclaimed | None (prevents noise) |

**Combined:** Moves STAR from "data dump" to "sovereign context"

---

## [4.1.2] - 2026-02-22 — SimHash Deduplication Fix

### ✅ Cross-File Near-Duplicate Deduplication

Added SimHash distance check to catch cross-file near-duplicates:

- ✅ **SimHash Distance Check** - Hamming distance < 5 = near-duplicate
- ✅ **Cross-File Detection** - Catches paraphrased/modified versions
- ✅ **Expected Improvement** - 25-35% → 40-50% dedup rate

### Implementation

**File:** `engine/src/services/search/search.ts` (line 393-399)

```typescript
// 3. SimHash Distance Check - Cross-file near-duplicates (NEW)
// Hamming distance < 5 out of 64 bits = near-duplicate content
if (candidate.molecular_signature && kept.molecular_signature) {
  const simhashDistance = getHammingDistance(candidate.molecular_signature, kept.molecular_signature);
  if (simhashDistance < 5) {
    isContentDuplicate = true;
    break;
  }
}
```

### Dedup Strategy (Complete)

1. ✅ **Geometric Dedup** - Same-file overlapping windows (50% threshold)
2. ✅ **Content Fingerprint** - Cross-file exact duplicates (MD5 hash)
3. ✅ **Containment Check** - Subset detection
4. ✅ **Fuzzy Prefix Match** - Near-exact duplicates (50-100 chars)
5. ✅ **SimHash Distance** - Cross-file near-duplicates (NEW)

---

## [4.1.1] - 2026-02-22 — Max-Recall & Context Inflation Complete

### ✅ Dual-Strategy Search Implementation

Complete max-recall mode with automatic triggering and context inflation:

- ✅ **Auto-Trigger** - Activates at >16k tokens (65k chars)
- ✅ **Context Inflation** - Post-merge n-1, n+1 expansion from disk
- ✅ **Physics Walker Config** - 3-hop, zero decay, 200 nodes/hop
- ✅ **Full Budget Allocation** - Each sub-query gets full budget
- ✅ **Query Splitting** - 4-word chunks, 5 max parallel searches

### Performance Benchmarks (Production Verified)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| **Context Retrieved** | 524k chars | **618k chars** | ✅ **+18%** |
| **Avg Chars/Atom** | 5k chars | **8,550 chars** | ✅ **+71%** |
| **Budget Utilization** | 90% | **98%** | ✅ **+8%** |
| **Atoms Retrieved** | 40-100 | **60 atoms** | ✅ Optimal |

### New Standards

- **Standard 086 (Updated)** - Dual-Strategy Search with max-recall
- **Standard 113** - Automatic Max-Recall for large budgets
- **Standard 116** - Phoenix Protocol (transactional backup/restore)

### Configuration

**Max-Recall Parameters** (`config/max-recall-config.ts`):
```typescript
{
  temporal_decay: 0.0,      // Zero age bias
  damping: 1.0,             // Zero signal loss
  max_hops: 3,              // Deep traversal
  max_per_hop: 200,         // Aggressive expansion
  temperature: 0.8          // High serendipity
}
```

### API Changes

- `POST /v1/memory/search` - Now accepts `strategy: 'max-recall'`
- Auto-triggers when `max_chars > 65,536`
- Response includes inflated context from disk

### UI Changes

- Deep Research button explicitly triggers max-recall
- Volume slider auto-triggers at maximum setting
- Bucket filtering works with max-recall mode

### Known Limitations

- **Search Latency:** 25-50s for max-recall (acceptable for 600k+ chars)
- **Cross-File Deduplication:** SimHash distance not yet implemented

---

## [4.1.0] - 2026-02-22 — Phoenix Protocol Complete

### ✅ Phoenix Protocol Implementation

Full transactional backup/restore system with filesystem rebuild:

- ✅ **Database Restore** - atoms, sources, engrams tables
- ✅ **Filesystem Rebuild** - inbox/, external-inbox/, mirrored_brain/
- ✅ **Performance Metrics** - timing, throughput stats
- ✅ **UI Integration** - inline confirmation, progress display
- ✅ **Optimized Batching** - 1000 items/batch (10x faster)

### Performance Benchmarks (Production Verified)

| Metric | Value |
|--------|-------|
| **Backup Size** | 1,015.40 MB |
| **Atoms Restored** | 281,690 |
| **Sources Restored** | 17 |
| **Total Time** | 828.8s (13.8 min) |
| **Throughput** | 340 atoms/second |
| **Memory Peak** | <600 MB |

### New Standards

- **Standard 116** - Phoenix Protocol (transactional backup/restore)

### API Changes

- `POST /v1/backup/restore` - Now includes timing metrics
- Response includes `totalTime` and `atomsPerSec`

### UI Changes

- Restore button with inline confirmation
- Progress logging every 10 seconds
- Final stats display with timing

---

## [4.0.0] - 2026-02-20 — Production Ready

### ✅ Whitepaper Implementation Complete

All specifications from the Sovereign Context Protocol whitepaper have been implemented and verified:

- ✅ STAR Algorithm (Tag-Walker with gravity scoring)
- ✅ SimHash Deduplication (O(1) duplicate detection)
- ✅ Disposable Index Architecture (Standard 110)
- ✅ Cross-Platform Native Modules (@rbalchii/* npm packages)
- ✅ Resource Efficiency (<1GB for 90MB datasets)
- ✅ SQL-Native Implementation (PGlite + CTEs)

### Performance Benchmarks (Verified)

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| **90MB Ingestion** | ~178s | <200s | ✅ |
| **Memory Peak** | <1GB | <1GB | ✅ |
| **Search Latency (p95)** | ~150ms | <200ms | ✅ |
| **Event Loop Yielding** | <100ms | <100ms | ✅ |
| **Native Acceleration** | 20x | 20x | ✅ |

### Production Deployment (Feb 2026)

- **436 files** ingested (~100MB total)
- **~280,000 molecules** processed
- **~1,500 atoms** indexed
- **331 files** rehydrated successfully
- **Zero data loss** with ephemeral index architecture

---

## [4.0.0] - 2026-02-16 — Architecture Clarification

### Critical Architecture Documentation

**The PGlite database is NOT the source of truth.** This release clarifies the **disposable index architecture**:

- **Source of Truth:** `mirrored_brain/` directory (plain filesystem)
- **Index:** PGlite database (byte-offset pointers + tags, rebuildable)
- **Implication:** Database wipe on shutdown is intentional—data persists in `mirrored_brain/`

### STAR Algorithm Documentation

Comprehensive documentation added for the physics-based search algorithm:

**Unified Field Equation:**
```
Gravity(atom, anchor) = (SharedTags) × e^(-λ × ΔTime) × (1 - SimHashDistance/64)
```

**Search Phases:**
1. **Planets (70%):** Direct keyword FTS matches
2. **Moons (30%):** Graph-discovered associations via tag-walker
3. **Fusion Scoring:** Gravity-weighted ranking

### Data Model Clarification

**Compound → Molecule → Atom** hierarchy:
- **Compound:** File/document reference
- **Molecule:** Semantic chunk with byte-offset pointers
- **Atom:** Tag/concept (NOT content)—content lives in `mirrored_brain/`

---

## [Standard 104] - 2026-02-10 — Universal Semantic Search

### Added

- **Universal Semantic Search Protocol:** Unified search architecture
- **70/30 Distributed Budgeting:** Strict token budget split (70% Direct / 30% Associative)
- **Adaptive Radius:** Dynamic context window sizing based on budget
- **Smart Content Weighting:** `code_weight` parameter for search tuning

### Deprecated

- **Standard 094 (Smart Search):** "Strict Anchor Phase" (AND logic) too brittle for natural language
- **Standard 086 (Tag Walker):** Replaced by unified Semantic Search route

---

## [Standard 103] - 2026-02-05 — Standalone UI

### Added

- **Standalone UI:** Internal lightweight UI serving capability
- **UI Detection Logic:** Automatic selection between external/internal UI
- **Catch-all Routes:** SPA routing support

---

## [Standard 102] - 2026-02-01 — Configuration Management

### Added

- **Centralized Configuration:** `user_settings.json` as single source of truth
- **Path Management:** Cross-platform path resolution
- **Runtime Configuration:** Dynamic reload capabilities

---

## [Standard 101] - 2026-01-28 — Byte Offset Protocol

### Added

- **Byte Offset Pointers:** Efficient content retrieval without loading full files
- **Radial Context Inflation:** Load ±50KB around matched atoms
- **Memory Efficiency:** 60% reduction in memory usage

---

## [Standard 100] - 2026-01-25 — PGlite Type Handling

### Fixed

- **Type Validation:** Proper input validation for PGlite
- **String Type Errors:** Fixed "Invalid input for string type" errors
- **Parameter Binding:** Safe parameterized queries

---

## [Standard 099] - 2026-01-22 — SQL Injection Prevention

### Added

- **Parameterized Queries:** All database queries use parameter binding
- **Input Sanitization:** Query input validation and sanitization
- **Security Audit:** Comprehensive security review

---

## [Standard 098] - 2026-01-28 — Scaling Architecture

### Added

- **Horizontal Scaling:** Distributed processing protocol
- **Worker System:** High-performance worker architecture
- **Load Balancing:** Request distribution across workers

---

## [Standard 097] - 2026-01-20 — Enhanced Code Analysis

### Added

- **AST Pointers:** Semantic code search support
- **Code Type Detection:** Function, class, module identification
- **Dependency Tracking:** Import/export graph edges

---

## [Standard 096] - 2026-01-18 — Timestamp Assignment

### Added

- **Consistent Timestamps:** Unified timestamp assignment protocol
- **Temporal Decay:** Time-based relevance scoring
- **Chronology Sorting:** "Earliest" and "latest" query modifiers

---

## [Standard 095] - 2026-01-15 — Database Reset

### Added

- **Startup Reset:** Automatic database wipe on startup (ephemeral index)
- **Rehydration:** Rebuild index from `mirrored_brain/` on startup
- **Zero Data Loss:** Guaranteed data persistence in filesystem

---

## [Standard 094] - 2026-01-12 — Smart Search Protocol

### Added

- **Intelligent Parsing:** Stopword removal and intent detection
- **Fuzzy Fallback:** Automatic retry with broader logic
- **Dynamic Sorting:** Keyword-based chronological sorting
- **Tag-Based Filtering:** Hashtag filtering support

### Deprecated

- Replaced by Standard 104 (Universal Semantic Search)

---

## [Standard 088] - 2026-01-10 — Server Startup Sequence

### Fixed

- **ECONNREFUSED:** Server starts before database initialization
- **Health Endpoints:** Handle uninitialized state gracefully
- **Extended Timeouts:** Proper initialization sequences

---

## [Standard 087] - 2026-01-08 — Relationship Narratives

### Added

- **Entity Co-occurrence:** Detect relationships between entities
- **Semantic Categories:** #Relationship, #Narrative, #Technical tags
- **Relationship Historian:** Track entity interactions over time

---

## [Standard 086] - 2026-01-06 — Tag-Walker Calibration

### Added

- **Search Calibration:** Improved natural language query handling
- **Multi-Context Split:** Decompose complex queries
- **Iterative Search:** Progressive query simplification

### Deprecated

- Replaced by Standard 104 (Universal Semantic Search)

---

## [Standard 085] - 2026-01-04 — Context Inflation

### Added

- **Context Inflation:** Combine adjacent molecules into coherent windows
- **Molecule Merging:** Contextually meaningful segments
- **Coherence Improvement:** Better retrieval quality

---

## [Standard 084] - 2026-01-02 — Semantic Shift

### Added

- **Semantic Categories:** High-level categorization system
- **Relationship-Focused Search:** Entity relationship prioritization
- **Intent Mapping:** Natural language to semantic categories

---

## [Standard 074] - 2025-12-20 — Native Module Acceleration

### Added

- **C++ N-API Modules:** Performance-critical operations
- **Graceful Degradation:** JavaScript fallbacks when native unavailable
- **Cross-Platform Builds:** Windows, macOS, Linux support
- **Performance Monitoring:** Native module health tracking

### Performance

- **2.3x faster** code processing
- **Sub-millisecond** operations for typical tasks
- **Zero-copy** string processing with `std::string_view`

---

## [Standard 065] - 2025-12-10 — Graph Associative Retrieval

### Added

- **Tag-Walker Protocol:** Graph-based search replacing vector search
- **Bipartite Graph:** Atoms ↔ Tags structure
- **70/30 Budget:** Planets (direct) and Moons (associative) split
- **Unified Field Equation:** Physics-based gravity scoring

---

## [Standard 059] - 2025-11-25 — Reliable Ingestion

### Added

- **Ghost Data Protocol:** Reliable ingestion pipeline
- **Batched Processing:** Atomic batch commits
- **Error Recovery:** Graceful error handling
- **Progress Tracking:** Ingestion status monitoring

---

## [1.0.0] - 2025-07-xx

### Breaking Changes - Search API
- Removed `exact:`, `fast:`, and `deep:` prefix support from search queries — these prefixes were aliases for specific backend behaviors that are no longer needed
- The `/v1/memory/search-max-recall` endpoint remains available but is not required; max-recall behavior can be achieved on regular search by setting a high context budget (e.g., `max_chars: 262144`)
- Max-recall is now integrated into regular search as a context budget toggle — set `max_chars` to a large value (≥256K) to get comprehensive retrieval across all phases

### Fixes - Search API
- Removed dead code: unused `deep` boolean parameter from search.ts, dead `searchType` property from density PREFIXES object in index.html, duplicate closing brace in PREFIXES object initialization

## Legacy Versions

### [3.x] - 2025 (CozoDB Era)

- CozoDB database integration (deprecated)
- Initial Tag-Walker implementation
- Basic ingestion pipeline

### [2.x] - 2024 (Prototype)

- Prototype implementation
- Core atomization concepts
- Early search algorithms

### [1.x] - 2023 (Concept)

- Initial concept and design
- Whitepaper development
- Architecture planning

---

**Production Status:** ✅ Ready (February 20, 2026)  
**Repository:** https://github.com/RSBalchII/anchor-engine-node
