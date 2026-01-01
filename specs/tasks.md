# Context-Engine Implementation Tasks

## Current Work Queue (Unified Anchor Architecture)

### Phase 5: Unified Anchor (Completed)
- [x] **Consolidation**: Merge File Server and Bridge into `webgpu_bridge.py` (Port 8000).
- [x] **Renaming**: `model-server-chat` -> `chat.html`, `neural-terminal` -> `terminal.html`.
- [x] **Cleanup**: Archive legacy startup scripts.
- [x] **Launcher**: Create `start-anchor.bat`.
- [x] **Native Shell Spawning**: Implement `/v1/system/spawn_shell` endpoint.
- [x] **Dashboard Integration**: Add Anchor Shell spawn button to `index.html`.
- [x] **Native Client**: Create `anchor.py` for PowerShell terminal spawning.
- [x] **Architecture Documentation**: Create Anchor Core specification.
- [x] **Testing Suite**: Create `test_model_loading.py` and `model_test.html` for endpoint verification.
- [x] **Troubleshooting Documentation**: Add model loading troubleshooting standard.

### Phase 5.1: Model Loading Fixes (Completed)
- [x] **URL Construction Fix**: Implement `/models/{model}/resolve/main/{file}` redirect endpoint for MLC-LLM compatibility.
- [x] **File Renaming**: Rename `root-mic.html` -> `anchor-mic.html`, `root-dreamer.html` -> `memory-builder.html`, `sovereign-db-builder.html` -> `db_builder.html`.
- [x] **UI Layout Fix**: Add proper margins to prevent elements from being cut off at top of browser window.
- [x] **Server Stability**: Fix server hanging issues caused by problematic path parameter syntax.
- [x] **Endpoint Verification**: Ensure all documented endpoints are accessible and responding properly.

### Phase 5.2: Search Enhancement (Completed)
- [x] **BM25 Implementation**: Replace regex-based search with CozoDB FTS using BM25 algorithm in `tools/chat.html`.
- [x] **Index Creation**: Add FTS index creation in `memory-builder.html`, `db_builder.html`, and `chat.html` initialization.
- [x] **Hybrid Search**: Maintain vector search alongside BM25 for semantic + lexical retrieval.
- [x] **Fallback Mechanism**: Implement regex fallback if FTS index is unavailable.
- [x] **Stemming Support**: Enable English stemming for better word variation matching.

### Phase 6: Text-Only + Watchdog Architecture (Completed)
- [x] **Vision Removal**: Remove brittle Vision/Ollama dependencies to increase survival rate.
- [x] **Watchdog Service**: Create `tools/watchdog.py` for passive text file monitoring.
- [x] **File Ingestion**: Implement `/v1/memory/ingest` endpoint in bridge for text ingestion.
- [x] **Debounce & Hash Check**: Add debounce and content hash checking to prevent duplicate ingestion.
- [x] **Auto-Resurrection**: Enhance `ResurrectionManager` to kill existing browser processes before launching new ones.
- [x] **Streaming CLI**: Update `anchor.py` to use streaming for better UX.
- [x] **Documentation Update**: Update architecture specs and standards to reflect new approach.

### Phase 7: Context Expansion & Persistence (Completed)
- [x] **Code File Support**: Expand watchdog to monitor code extensions (.py, .js, .html, etc.)
- [x] **Browser Profile Cleanup**: Add unique temp profiles and cleanup for browser processes
- [x] **Chat Session Persistence**: Auto-save conversations to context/sessions/ directory
- [x] **Ingestion Loop Closure**: Ensure chat sessions become ingested context automatically
- [x] **Memory Leak Prevention**: Implement profile cleanup to prevent disk space issues
- [x] **Documentation Update**: Create new standards 019-021 for new features

### Phase 8: Session Recorder & Text-File Source of Truth (Completed)
- [x] **Daily Session Files**: Create `chat_YYYY-MM-DD.md` files for each day's conversations
- [x] **Text-File Source of Truth**: Implement "Database is Cache" philosophy
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

## Backlog
- [ ] **Federation Protocol**: P2P sync.
- [ ] **Android App**: Wrapper for Root Coda.