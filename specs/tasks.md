# Context-Engine Implementation Tasks

## Current Work Queue

## Active Sprint: Operation "Iron Lung" (Native Refactor)

### Phase 21: The Native Bridge (C++ / N-API) - **COMPLETED** ✅
- [x] **Infrastructure Setup**:
    - [x] Install `node-addon-api` and `node-gyp`.
    - [x] Configure `binding.gyp` for C++17 support.
    - [x] Create `src/native/` directory structure.
- [x] **Module 1: The Key Assassin (Text Hygiene)**:
    - [x] Define `src/native/key_assassin.hpp` (Header).
    - [x] Implement `src/native/key_assassin.cpp` (Zero-copy cleaning logic).
    - [x] Implement `src/native/main.cpp` (N-API exports).
    - [x] **Verification**: Compile and run `npm test` to verify binary loading.
- [x] **Module 2: The Atomizer (Text Splitting)**:
    - [x] Implement `src/native/atomizer.hpp` and `src/native/atomizer.cpp`.
    - [x] Implement streaming text splitter with prose/code strategies.
    - [x] **Verification**: Benchmark performance improvements.
- [x] **Module 3: The Fingerprint (Deduplication)**:
    - [x] Implement `src/native/fingerprint.hpp` and `src/native/fingerprint.cpp`.
    - [x] Implement SimHash algorithm for fuzzy matching.
    - [x] Implement Hamming distance calculation.
- [x] **Integration**:
    - [x] Refactor `engine/src/services/ingest/refiner.ts` to import and use the native module.
    - [x] Update `engine/src/services/ingest/atomizer.ts` with native acceleration.
    - [x] Update `engine/src/core/db.ts` to include `simhash` column.
    - [x] Update `engine/src/services/ingest/ingest.ts` to handle simhash values.
    - [x] **Benchmark**: Compare `KeyAssassin` (C++) vs `cleanseJsonArtifacts` (JS) on a 10MB log file. (2.3x improvement achieved)
- [x] **Testing**:
    - [x] Create comprehensive test suite: `engine/tests/test_native_modules.js`
    - [x] Create integration test suite: `engine/tests/test_native_integration.js`
    - [x] Verify all native functions work correctly.
- [x] **Documentation**:
    - [x] Create Standard 074: Native Module Accelereration (The "Iron Lung" Protocol)
    - [x] Update README with native module architecture.

### 🟡 High Priority (Queue)
- [ ] **Module 4: The Ingestor**: Replace `cheerio` with lightweight C++ HTML parser (future).
- [ ] **Performance Monitoring**: Implement runtime performance tracking for native modules.
- [ ] **Cross-Platform Validation**: Verify native modules work on Linux/macOS.

### Phase 20: Tag-Walker & Mirror 2.0 (Completed ✅)
- [x] **Tag-Walker Protocol**: Replaced Vector Search with 3-phase graph retrieval (FTS -> Pivot -> Walk).
- [x] **Mirror 2.0**: Implemented semantic filesystem projection with `@bucket/#tag` layout.
- [x] **Cleanup logic**: Added wipe-on-sync to `mirrored_brain` to prevent stale data.
- [x] **FTS Hardening**: Implemented `sanitizeFtsQuery` to prevent parser crashes. (Standard 066)
- [x] **Licensing Alignment**: Updated project to Elastic License 2.0.

### 🔴 Critical (Immediate)
- [x] **Database Indices**: Add `tags`, `buckets`, `epochs` indices to `db.ts` (Critical Performance Fix).
- [x] **Build Fixes**: Resolve implicit `any` errors in `api.ts`.
- [x] **Runtime Fixes**: Fix "Symbol score unbound" error in `api.ts`.
- [x] **Fix "JSON Vomit" (Session Pollution):** Implement Side-Channel Separation for Intent Translation. (Standard 055)
- [x] **Fix Search Crash:** Handle `null` returns from Intent Translation in `api.js`.
- [x] **Fix "No Sequences Left":** Explicitly dispose Side-Channel sessions and increase sequence limit.
- [x] **Sovereign Desktop UI:** Implement "Frosted Glass" transparent overlay. (Standard 056)
- [x] **Vision Integration:** detailed screen capture via `desktopCapturer` in the Overlay.
- [x] **Refactor Inference Monolith:** Deconstruct `inference.js` into modular TypeScript services (`provider.ts`, `context.ts`, `inference.ts`).
- [x] **Magic Inbox:** Implement "Drop-Zone" pattern in `watcher.ts` (Watch -> Ingest -> Archive).
- [x] **Hybrid Module Stability:** Revert to CJS with Dynamic Imports for robust ESM compatibility.

### 🟡 High Priority (This Week)
- [ ] **Backend Vision Pipeline:** Ensure `inference.js` correctly handles the `{type: image_url}` message format via `node-llama-cpp`.
- [ ] **Context Assembly Speed:** Investigate caching strategies for repeated Large Contexts.
- [ ] **Dreamer Upgrade:** Enable "Deep Sleep" logic for aggressive deduplication.

### 🟢 Backlog (Feature Requests)
- [ ] **Voice Input:** Whisper integration for the Desktop Overlay.
- [ ] **Codebase Map:** Visual graph of the `context/` directory.
- [ ] **MCP Server:** Expose ECE as a Model Context Protocol server.

### Phase 17: Enterprise Library Architecture (In Progress)
- [x] **Context Cartridges UI:** Implemented "Loadout" buttons in `index.html` (Architect/Python/Whitepaper).
- [x] **Logical Notebooks:** Updated `context_packer.js` to treat `context/libraries/` as auto-tagged cartridges.
- [x] **Watcher Upgrades:** Updated `watcher.js` to detect Library folders and apply `#{lib}_docs` buckets.
- [x] **Stability Fix:** Patched `inference.js` (Sequences: 15) to prevent VRAM exhaustion with concurrent Dreamer/Search.
- [x] **Whitepaper Context:** Injected `specs/` into the graph as a dedicated `specs` bucket.
- [ ] **Dynamic Loadouts:** Move Loadout config from `sovereign.yaml` (Updated from index.html).
- [ ] **Docs Update:** Create `README_LIBRARIES.md` explaining how to add new cartridges.

### Phase 19: Enterprise & Advanced RAG (Planned)
- [ ] **Feature 7: Backup & Restore**: Server-side DB dumps (`POST /v1/backup`) and Restore-on-Boot logic.
- [ ] **Feature 8: Rolling Context Slicer**: Middle-Out context budgeting for `ContextManager` (Relevance vs Recency).
- [ ] **Feature 9: Live Context Visualizer**: "RAG IDE" in Frontend with real-time budget slider and atom visualization.
- [ ] **Feature 10: Sovereign Provenance**: Trust hierarchy (Sovereign vs External) with bias toggle in Search.

### Phase 18: Monorepo & Configuration Unification (Active)
- [x] **PNPM Migration:** Converted project to `pnpm` workspace (packages: engine, desktop-overlay, shared).
- [x] **Shared Types:** Created `@ece/shared` for unified TypeScript interfaces.
- [x] **Unified Config:** Implemented `sovereign.yaml` as Single Source of Truth for Models, UI, and Network.
- [x] **Lifecycle Management:** Electron Main now automatically spawns/kills the Engine process.
- [x] **Settings UI:** Added `Settings.tsx` overlay with IPC read/write to `sovereign.yaml`.
- [ ] **Security Hardening:** Migrate IPC to `contextBridge` / `preload.js` (disable `nodeIntegration`).

### Phase 16: Brain Link & Sovereign Desktop (Done)
- [x] **Schema Introspection Fix**: Use `::columns memory` instead of broken `*columns{...}` query (Standard 053)
- [x] **FTS Persistence**: FTS index now survives restarts (no more migration loop)
- [x] **Brain Link UI**: Auto-context injection in `chat.html` with memory budget slider
- [x] **Personal Memory Ingestion**: Created `add_personal_memories.js` for test data
- [x] **Planning Document**: Created `specs/sovereign-desktop-app.md` with full architecture
- [x] **Chat UI Overhaul**: Simplified chat.html - removed Brain Link (unreliable local), kept Manual Context
- [x] **Streaming Tokens**: Real-time token streaming display as LLM generates response
- [x] **Thinking/Answer Separation**: Model `<think>` blocks displayed separately with purple styling
- [x] **User Message Fix**: User prompts now persist correctly in chat history

### Phase 12: Production Polish (Completed)
- [x] **Post-Migration Safety**: Implement emergency backups before schema changes (`db.js`).
- [x] **API Fortification**: Add input validation for `ingest` and `search` endpoints (`api.js`).
- [x] **Search Resiliency**: Fix bucket-filtering bypass in `executeSearch`.
- [x] **Verification Suite**: 100% pass rate on `npm test`.
- [x] **Chat Cockpit Enhancement**: Add conversation history persistence to `chat.html`
- [x] **Streaming Responses**: Implement SSE for real-time token streaming
- [x] **One-Click Install**: Create `setup.ps1` / `setup.sh` scripts

### Phase 11: Markovian Reasoning Engine (Completed)
- [x] **Scribe Service**: Created `engine/src/services/scribe.js` for rolling state
- [x] **Context Weaving**: Upgraded `inference.js` to auto-inject session state
- [x] **Test Suite**: Created `engine/tests/suite.js` for API verification
- [x] **Benchmark Tool**: Created `engine/tests/benchmark.js` for accuracy testing
- [x] **Config Fixes**: Externalized MODELS_DIR, fixed package.json typo
- [x] **API Endpoints**: Added `/v1/scribe/*` and `/v1/inference/status`
- [x] **Standard 041**: Documented Markovian architecture

### Phase 13: Epochal Historian & Mirror Protocol Enhancement (Completed)
- [x] **Epochal Historian Implementation**: Implement recursive decomposition (Epochs -> Episodes -> Propositions) in Dreamer service
- [x] **Mirror Protocol Enhancement**: Update to prioritize Epoch-based structure in `context/mirrored_brain/[Bucket]/[Epoch]/[Memory_ID].md`
- [x] **Documentation Updates**: Update `specs/spec.md`, `specs/search_patterns.md`, and `specs/context_assembly_findings.md` with Epochal Historian details
- [x] **Watcher Shield**: Ensure file watcher ignores `context/mirrored_brain/` to prevent recursive loops

### Phase 14: Path Resolution Fixes (Completed)
- [x] **Service Module Path Corrections**: Fix relative import paths in all service files (search, ingest, scribe, dreamer, mirror, inference, watcher, safe-shell-executor)
- [x] **Core Module References**: Correct paths from `'../core/db'` to `'../../core/db'` in services located in subdirectories
- [x] **Configuration Imports**: Standardize all relative imports to properly reference core modules and configuration files
- [x] **Module Loading Verification**: Verify all modules load without "Cannot find module" errors

### Phase 15: Schema Evolution & Epochal Historian Enhancement (Completed)
- [x] **Database Schema Update**: Add `epochs: String` field to memory table schema to store epochal classifications
- [x] **Dreamer Service Update**: Modify database queries and updates to include epochs field in processing
- [x] **Search Service Update**: Modify database queries to include epochs field in search operations
- [x] **Mirror Service Update**: Ensure epochs field is properly handled in mirroring operations
- [x] **Documentation Updates**: Update `specs/spec.md`, `specs/search_patterns.md`, and `specs/context_assembly_findings.md` with schema changes

### Phase 16: Brain Link & Sovereign Desktop (In Progress)
- [x] **Schema Introspection Fix**: Use `::columns memory` instead of broken `*columns{...}` query (Standard 053)
- [x] **FTS Persistence**: FTS index now survives restarts (no more migration loop)
- [x] **Brain Link UI**: Auto-context injection in `chat.html` with memory budget slider
- [x] **Personal Memory Ingestion**: Created `add_personal_memories.js` for test data
- [x] **Planning Document**: Created `specs/sovereign-desktop-app.md` with full architecture
- [x] **Chat UI Overhaul**: Simplified chat.html - removed Brain Link (unreliable local), kept Manual Context
- [x] **Streaming Tokens**: Real-time token streaming display as LLM generates response
- [x] **Thinking/Answer Separation**: Model `<think>` blocks displayed separately with purple styling
- [x] **User Message Fix**: User prompts now persist correctly in chat history
- [ ] **Sovereign Desktop Prototype**: Electron overlay with hotkey activation
- [ ] **Screen Capture Integration**: Add VL model for screen understanding
- [ ] **Proactive Memory**: Auto-ingest screen context and conversation highlights
- [ ] **Distribution**: Installer, auto-update, first-run wizard

### Phase 10: Cortex Upgrade (Completed)
- [x] **Multi-Bucket Schema**: Migrate from single `bucket` to `buckets: [String]` (Standard 039).
- [x] **Dreamer Service**: Implement background self-organization via local LLM.
- [x] **Cozo Hardening**: Resolve list-handling and `unnest` syntax errors (Standard 040).
- [x] **ESM Interop**: Fix dynamic import issues for native modules in CJS.

- [x] **Cross-Machine Sync**: Enable file sync via Dropbox/Git for multi-device access
- [x] **Infinite Loop**: Create feedback loop: Chat -> File -> Ingestion -> Memory -> Next Chat
- [x] **Timestamped Entries**: Format messages with timestamps for better tracking
- [x] **Session Tracking**: Add session file path display in CLI startup

### Completed - Root Refactor ✅
- [x] **Kernel**: Implement `tools/modules/sovereign.js`.
- [x] **Mic**: Refactor `root-mic.html` to use Kernel.
- [x] **Builder**: Refactor `sovereign-db-builder.html` to use Kernel.
- [x] **Console**: Refactor `model-server-chat.html` to use Kernel (Graph-R1).
- [x] **Docs**: Update all specs to reflect Root Architecture.

### Completed - Hardware Optimization 🐉
- [x] **WebGPU Buffer Optimization**: Implemented 256MB override for Adreno GPUs.
- [x] **Model Profiles**: Added Lite, Mid, High, Ultra profiles.
- [x] **Crash Prevention**: Context clamping for constrained drivers.
- [x] **Mobile Optimization**: Service Worker (`llm-worker.js`) for non-blocking inference.
- [x] **Consciousness Semaphore**: Implemented resource arbitration in `sovereign.js`.

### Completed - The Subconscious ✅
- [x] **Root Dreamer**: Created `tools/root-dreamer.html` for background memory consolidation.
- [x] **Ingestion Refinement**: Upgraded `read_all.py` to produce LLM-legible YAML.
- [x] **Root Architecture Docs**: Finalized terminology (Sovereign -> Root).
- [x] **Memory Hygiene**: Implemented "Forgetting Curve" in `root-dreamer.html`.

### Completed - Active Cognition ✅
- [x] **Memory Writing**: Implement `saveTurn` to persist chat to CozoDB.
- [x] **User Control**: Add "Auto-Save" toggle to System Controls.
- [x] **Temporal Grounding**: Inject System Time into `buildVirtualPrompt`.
- [x] **Multimodal**: Add Drag-and-Drop Image support to Console.

### Phase 4.1: The Neural Shell (Completed) 🚧
**Objective:** Decouple Intelligence (Chat) from Agency (Terminal).
- [x] **Phase 1:** "Stealth Mode" Cache Bypass (Completed).
- [x] **Phase 2:** Headless Browser Script (`launch-ghost.ps1`) (Completed).
- [x] **Phase 3:** `sov.py` Native Client Implementation.
- [x] **Phase 3.5:** Ghost Auto-Ignition (Headless auto-start with ?headless=true flag).
- [x] **Phase 4:** Migration to C++ Native Runtime (Removing Chrome entirely).
- [x] **Bridge Repair**: Debug and stabilize `extension-bridge` connectivity.
- [x] **Neural Shell Protocol**: Implement `/v1/shell/exec` in `webgpu_bridge.py`.
- [x] **The "Coder" Model**: Add `Qwen2.5-Coder-1.5B` to Model Registry.
- [x] **Terminal UI**: Create `tools/neural-terminal.html` for natural language command execution.

### Phase 4.2: Agentic Expansion (Deferred)
- [ ] **Agentic Tools**: Port Verifier/Distiller logic to `tools/modules/agents.js`.
- [ ] **Voice Output**: Add TTS to Console.

## Phase 5: The Specialist Array
- [ ] **Dataset Generation**: Samsung TRM / Distillation.
- [ ] **Unsloth Training Pipeline**: RTX 4090 based fine-tuning.
- [ ] **Model Merging**: FrankenMoE construction.

## Phase 6: GPU Resource Management (Completed)
- [x] **GPU Queuing System**: Implement `/v1/gpu/lock`, `/v1/gpu/unlock`, and `/v1/gpu/status` endpoints with automatic queuing
- [x] **Resource Conflict Resolution**: Eliminate GPU lock conflicts with proper queue management
- [x] **503 Error Resolution**: Fix "Service Unavailable" errors by implementing proper resource queuing
- [x] **Sidecar Integration**: Add GPU status monitoring to sidecar interface
- [x] **Log Integration**: Add GPU resource management logs to centralized logging system
- [x] **Documentation**: Update specs and standards to reflect GPU queuing system

## Phase 7: Async/Await Best Practices (Completed)
- [x] **Coroutine Fixes**: Resolve "coroutine was never awaited" warnings in webgpu_bridge.py
- [x] **Event Loop Integration**: Properly integrate async functions with FastAPI's event loop
- [x] **Startup Sequence**: Ensure logging system initializes properly with application lifecycle
- [x] **Resource Management**: Fix resource cleanup in WebSocket handlers to prevent leaks
- [x] **Error Handling**: Enhance async error handling with proper cleanup procedures
- [x] **Documentation**: Create Standard 014 for async/await best practices

## Phase 8: Browser-Based Control Center (Completed)
- [x] **Sidecar UI**: Implement `tools/sidecar.html` with dual tabs for retrieval and vision
- [x] **Context UI**: Implement `tools/context.html` for manual context retrieval
- [x] **Vision Engine**: Create `tools/vision_engine.py` for Python-powered image analysis
- [x] **Bridge Integration**: Update `webgpu_bridge.py` to serve UI and handle vision endpoints
- [x] **Endpoint Implementation**: Add `/v1/vision/ingest`, `/v1/memory/search`, `/logs/recent` endpoints
- [x] **File-based Logging**: Implement persistent logging to `logs/` directory with truncation
- [x] **Documentation**: Update specs and standards to reflect new architecture

### Phase 9: Anchor Lite Refactor (Completed)
- [x] **Consolidation**: Simplified system to Single Source of Truth (`context/`) -> Single Index (CozoDB) -> Single UI (`context.html`).
- [x] **Cleanup**: Archived unused tools (`db_builder`, `memory-builder`, `sidecar`, `mobile-chat`).
- [x] **Engine Refactor**: Created headless `ghost.html` engine with WebSocket bridge.
- [x] **Launch Logic**: Unified startup in `start-anchor.bat` and `webgpu_bridge.py`.
- [x] **Standard 023**: Documented "Anchor Lite" architecture and "Triangle of Pain".

### Phase 10: Context Ingestion Pipeline Fixes (Completed)
- [x] **Field Name Alignment**: Fixed mismatch between watchdog payload (`filetype`) and endpoint expectation (`file_type`)
- [x] **Source Identification**: Updated watchdog to send proper source identifiers instead of "unknown"
- [x] **Ghost Engine Update**: Fixed handleIngest function to use correct field names (`msg.file_type`)
- [x] **Error Handling**: Enhanced error reporting in watchdog for better debugging
- [x] **Database Initialization**: Verified CozoDB schema creation and memory table initialization
- [x] **Ingestion Verification**: Confirmed context files are properly ingested and searchable

### Phase 11: Script Running Protocol Implementation (Completed)
- [x] **Protocol Creation**: Created `SCRIPT_PROTOCOL.md` with guidelines to prevent getting stuck in long-running loops
- [x] **System Optimization**: Fixed database paths and search queries for better performance
- [x] **Documentation Update**: Updated doc_policy to include protocol as allowed root document
- [x] **Standards Creation**: Created Standards 035 and 036 for detached execution and log management
- [x] **Startup Scripts**: Created proper detached startup scripts with logging

## Backlog
- [ ] **Federation Protocol**: P2P sync.
- [ ] **Android App**: Wrapper for Root Coda.