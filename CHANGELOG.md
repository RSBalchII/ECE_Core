# Context-Engine Changelog

## [2.3.0] - 2026-01-01 "Stability & Passive Text Ingestion"

### Added
- **Auto-Resurrection System**: Ghost Engine (headless browser) automatically restarts on WebSocket disconnect
  - `ResurrectionManager` class handles browser lifecycle
  - Retry logic: 3 attempts with 2-second delays
  - Comprehensive logging of resurrection events
  - Works on Windows (Edge/Chrome) and Linux/Mac (Chrome)
- **Passive Context Ingestion**: New `watchdog.py` service for continuous context growth
  - Monitors `context/` folder for `.txt`, `.md`, `.markdown` files
  - Batch processing with configurable interval (default 5s)
  - Real-time mode (watchdog library) and polling mode (fallback)
  - `/v1/memory/ingest` endpoint for receiving ingested files
- **Model Server Improvements**: Enhanced `/models/{file_path:path}` endpoint
  - Proper streaming for large binary files
  - Correct MIME type handling (`.wasm`, `.safetensors`, `.json`, etc.)
  - Path traversal protection
  - Range request support with proper headers
  - 1-week cache TTL for immutable model files

### Fixed
- **Model Loading**: All `chat.html` appConfig instances now use local bridge URLs
  - Ensures reliable local model loading
  - Fallback to HuggingFace only when files not available locally
  - Prevents 404 errors from hardcoded external URLs
- **Connection Stability**: WebSocket handler properly triggers auto-resurrection
  - Cleans up pending requests before restart
  - Prevents orphaned request queues
- **File Size Validation**: Watchdog service enforces max 1MB file size (configurable)
- **Security**: Added path validation to prevent directory traversal attacks

### Changed
- **Architecture**: Pivot from Vision/Ollama to Text-Only + Watchdog model
  - Removed heavy Vision processing pipeline
  - Simplified to pure text ingestion for stability
  - Focus on reliable model serving and auto-recovery
- **Model Configuration**: Unified model URL scheme across all UI components
  - All models now served via local bridge redirect
  - Consistent URL format: `window.location.origin + "/models/{model_id}/resolve/main/"`
- **Logging**: Enhanced logging system with per-component log files
  - `logs/webgpu_bridge.log`
  - `logs/resurrection.log`
  - `logs/memory_api.log`
  - `logs/model_server.log`

### Removed
- Vision processing pipeline (Ollama integration)

## [2.3.1] - 2026-01-01 "Process Management & Streaming UX"

### Added
- **Enhanced Process Management**: Improved `ResurrectionManager` with process cleanup
  - `kill_existing_browsers()` method to terminate existing browser processes before launching new ones
  - Explicit `--remote-debugging-port=9222` flag to prevent port conflicts
  - Increased initialization wait time from 3 to 5 seconds
- **File Ingestion Improvements**: Enhanced `watchdog.py` with debounce and hash checking
  - Debounce functionality to wait for silence before processing file changes
  - MD5 hash checking to prevent duplicate ingestion of unchanged files
  - Proper cleanup of debounce timers
- **Streaming CLI Client**: Updated `anchor.py` to use streaming for better UX
  - Changed from `stream=False` to `stream=True` for real-time character display
  - Added line-by-line processing of streaming responses
  - Maintained conversation history accumulation while providing immediate feedback
- **New Standards**: Added Standards 016-018 for process management, file ingestion, and streaming UX

### Fixed
- **Zombie Process Risk**: Fixed issue where browser resurrection would fail due to port conflicts
- **Autosave Flood**: Fixed excessive database writes from editor autosave features
- **CLI Latency**: Fixed hanging terminal during long model responses

### Changed
- **Process Management**: Enhanced browser process management with proper cleanup
- **File Ingestion**: Improved file monitoring with debounce and hash checking
- **CLI UX**: Enhanced terminal experience with streaming responses

## [2.3.2] - 2026-01-01 "Ingestion Expansion & Memory Persistence"

### Added
- **Code File Support**: Extended `watchdog.py` to monitor code extensions
  - Added `.py`, `.js`, `.html`, `.css`, `.json`, `.yaml`, `.yml`, `.sh`, `.bat`, `.ts`, `.tsx`, `.jsx`, `.xml`, `.sql`, `.rs`, `.go`, `.cpp`, `.c`, `.h`, `.hpp` to monitored extensions
- **Browser Profile Cleanup**: Enhanced `ResurrectionManager` with temporary profile management
  - Added `--user-data-dir` with unique timestamp to prevent profile conflicts
  - Added `_cleanup_old_profiles()` method to remove old temporary directories
  - Added performance optimization flags for headless browser
- **Chat Session Persistence**: Updated `anchor.py` to auto-save conversations
  - Created `context/sessions/` directory for chat logs
  - Added `save_message_to_session()` to persist each message to markdown files
  - Ensures conversation history survives CLI crashes and becomes ingested context

### Fixed
- **Ingestion Blind Spot**: Fixed system being blind to code files in user's context
- **Memory Leak Risk**: Fixed potential disk space issues from temporary browser profiles
- **Lost Context Risk**: Fixed loss of conversation history on CLI crashes

## [2.3.3] - 2026-01-01 "Session Recorder & Text-File Source of Truth"

### Added
- **Daily Session Files**: Updated `anchor.py` to create daily markdown files (`chat_YYYY-MM-DD.md`)
  - Uses `ensure_session_file()` to create dated session files
  - Formats messages with timestamps: `### ROLE [HH:MM:SS]`
  - Stores in `../context/sessions/` directory relative to tools/
- **Text-File Source of Truth**: Implemented "Database is Cache" philosophy
  - All chat history saved to text files for cross-machine sync
  - Files automatically ingested by watchdog service
  - Creates infinite feedback loop: Chat -> File -> Ingestion -> Memory -> Next Chat
- **Session Tracking**: Added session file path display in CLI startup

### Changed
- **File Structure**: Changed from timestamped individual files to daily consolidated files
- **Relative Pathing**: Uses relative path (`../context/sessions/`) for proper directory structure
- **Markdown Format**: Improved formatting with headers and timestamps for better readability

## [2.2.12] - 2025-12-31 "UI Endpoint Fixes & Log File Verification"

### Fixed
- **UI Endpoints**: Fixed `/context` and `/sidecar` endpoints to properly serve HTML files with correct paths
- **File Response**: Corrected FileResponse paths to use absolute paths for reliable file serving
- **Endpoint Accessibility**: Resolved 500 errors for UI endpoints by fixing file path resolution
- **Static File Serving**: Enhanced static file serving for HTML interfaces

### Changed
- **Path Resolution**: Updated endpoint handlers to use proper absolute path resolution for static files
- **UI Serving**: Improved reliability of UI file serving from the bridge
- **Error Handling**: Enhanced error handling for file serving operations

## [2.2.11] - 2025-12-31 "Coroutines and Async Fixes"

### Fixed
- **Async Warnings**: Fixed "coroutine was never awaited" warnings by properly implementing startup event handlers
- **Event Loop Integration**: Corrected async function calls to work properly with FastAPI's event loop

- **Resource Management**: Fixed resource cleanup in WebSocket handlers to prevent leaks
- **Startup Sequence**: Ensured logging system initializes properly with the application lifecycle

### Changed
- **Async Handling**: Improved async/await patterns throughout the bridge for better stability
- **Error Handling**: Enhanced error handling for async operations with proper cleanup
- **Initialization**: Refined startup sequence to ensure all components initialize correctly

## [2.2.10] - 2025-12-31 "Log File System Implementation"

### Added
- **Logs Directory**: Created `logs/` directory to store individual component logs
- **File-based Logging**: Each system component now writes to its own log file (e.g., `chat-api.log`, `memory-api.log`, `websocket-bridge.log`)
- **Log Truncation**: Implemented automatic log truncation to keep only last 1000 lines per file
- **Individual Log Files**: Separate log files for each component for easier debugging

### Changed
- **Log Storage**: Moved from in-memory only to file-based persistent logging
- **Log Management**: Added automatic log rotation and truncation to prevent disk space issues
- **API Endpoints**: All API endpoints now write to both central buffer and individual log files

## [2.2.9] - 2025-12-31 "Complete Process Log Capture"

### Added
- **Process Logging**: Added logging for all major system processes (chat, memory search, WebSocket connections)
- **Error Tracking**: Enhanced error logging with detailed context and request IDs
- **Status Monitoring**: Added detailed status messages for connection states and process flow

### Changed
- **Log Collection**: Enhanced centralized log collection with comprehensive process monitoring
- **API Endpoints**: All API endpoints now log detailed request/response information
- **WebSocket Handler**: Improved WebSocket connection logging with detailed status updates
- **Error Handling**: Enhanced error messages with better context and correlation IDs

## [2.2.8] - 2025-12-31 "Universal Log Collection System"

### Added
- **Log Collection**: Added centralized log collection system in `webgpu_bridge.py` with global log buffer
- **API Endpoints**: Added `/logs/recent` and `/logs/collect` endpoints for log aggregation
- **Standard 013**: Created universal log collection standard for all system components
- **Cross-Platform Logging**: Implemented logging from all system components (Python, JavaScript, WebSocket)

### Changed
- **Log Viewer**: Updated `log-viewer.html` to consume logs from the new centralized endpoint
- **WebSocket Logging**: Enhanced WebSocket connection to send detailed status messages to log viewer
- **System Integration**: All components now route logs through the central collection system

## [2.2.7] - 2025-12-31 "Ghost Engine Startup Improvements"

### Fixed
- **Connection Issues**: Fixed Ghost Engine startup to ensure proper WebSocket connection establishment
- **Process Launch**: Improved startup scripts to properly launch Ghost Engine with correct parameters
- **CPU-Only Mode**: Enhanced CPU-only mode startup with appropriate browser flags
- **Low-Resource Mode**: Fixed low-resource mode startup with conservative GPU settings

### Changed
- **Startup Scripts**: Updated `start-anchor.bat` and `start-low-resource.bat` with better Ghost Engine launch parameters
- **Connection Timing**: Improved timing between server and Ghost Engine startup
- **User Feedback**: Added clearer status messages during startup process

## [2.2.6] - 2025-12-31 "WebGPU Adapter Error Handling"

### Fixed
- **WebGPU Errors**: Added specific handling for "No WebGPU Adapter found" errors on Snapdragon/limited GPU devices
- **Error Messages**: Improved error messages to guide users when WebGPU is unavailable
- **Graceful Degradation**: System now provides helpful guidance instead of failing silently

### Changed
- **Chat Endpoint**: Enhanced `/v1/chat/completions` to handle WebGPU adapter errors gracefully
- **Error Response**: More informative error messages for GPU-related issues
- **User Guidance**: Clear instructions for users with unsupported GPU configurations

## [2.2.5] - 2025-12-31 "Log Viewer Consolidation"

### Added
- **Single Panel**: Consolidated all logs into one unified panel for easier monitoring
- **Stream Collection**: All app processes now stream to single consolidated view
- **Efficiency**: Removed unused chat and context panels that were empty

### Changed
- **Log Viewer**: `tools/log-viewer.html` now shows all logs in single panel
- **UI Simplification**: Streamlined interface for better usability
- **Copy Functionality**: Simplified copy to clipboard for all logs at once

## [2.2.4] - 2025-12-31 "Chat Client & Bridge Reorientation"

### Added
- **Chat Client**: Converted `tools/anchor.py` from Shell Executor to Chat Client interface
- **Stream Accumulation**: Enhanced bridge to properly accumulate chat stream responses
- **Terminal Chat**: Added conversation history and context management to CLI

### Fixed
- **Chat Response**: Fixed issue where chat responses were cut off due to stream handling
- **Bridge Protocol**: Improved WebSocket message handling for complete response delivery
- **Conversation Flow**: Added proper conversation history management in CLI

### Changed
- **Architecture**: Shifted from command execution to chat interface in terminal client
- **API Handling**: Bridge now accumulates streaming responses for non-streaming API compatibility
- **User Experience**: Terminal client now provides full chat experience with context

## [2.2.3] - 2025-12-31 "Ghost Engine Startup Fix"

### Fixed
- **JavaScript Disabled**: Removed `--disable-javascript` flag that was preventing Ghost Engine from starting
- **WASM Engine**: Fixed issue where WebAssembly AI engine couldn't load with JavaScript disabled
- **WebSocket Connection**: Resolved "Failed to fetch" errors by enabling JavaScript in headless browser
- **Memory Search**: Fixed context search functionality by ensuring Ghost Engine starts properly

### Changed
- **Startup Scripts**: Updated `start-anchor.bat` and `start-low-resource.bat` to enable JavaScript
- **Ghost Engine**: Headless browser now properly loads WASM AI engine and connects to bridge

## [2.2.2] - 2025-12-31 "Context Search Fix"

### Fixed
- **Memory Search**: Fixed 503 errors when Ghost Engine is disconnected by providing helpful error messages
- **WebSocket Handling**: Improved handling of search result responses from Ghost Engine
- **Timeout Management**: Added proper timeout handling for search requests
- **Error Messages**: Enhanced error messages to guide users when Ghost Engine is not connected

### Changed
- **Search Endpoint**: Improved `/v1/memory/search` to handle disconnected Ghost Engine gracefully
- **Chat Endpoint**: Enhanced error handling for chat completions when Ghost Engine is unavailable

## [2.2.1] - 2025-12-31 "UI Consolidation"

### Removed
- **Sidecar Interface**: Removed duplicate sidecar.html interface to consolidate to single Context UI
- **Redundant Endpoints**: Streamlined UI access to focus on single interface

### Added
- **Context UI**: Single, focused interface for retrieval and search functionality
- **Endpoint Consolidation**: Both `/sidecar` and `/context` now serve the same Context UI

### Changed
- **UI Strategy**: Shifted from multiple similar interfaces to single, focused Context UI
- **User Experience**: Simplified navigation with single interface for context retrieval

## [2.2.0] - 2025-12-31 "Text-Only Architecture Pivot"

### Removed
- **Vision Engine**: Removed Python-based vision_engine.py and Ollama dependency
- **Image Processing**: Removed all /v1/vision/* endpoints and image-related functionality
- **External Dependencies**: Eliminated heavy Python/Ollama dependencies for lightweight operation

### Added
- **Text-Only Focus**: Streamlined architecture focusing purely on text context and memory
- **Simplified Bridge**: Cleaned webgpu_bridge.py with only essential context relay functionality
- **Memory Builder**: Reinforced tools/memory-builder.html as the primary background processor
- **Browser-Native Processing**: Leverage Ghost Engine (WebGPU) for all processing needs

### Changed
- **Architecture**: Shifted from multi-component system to lightweight, browser-native approach
- **Processing Model**: Memory processing now handled by Qwen 1.5B in WebGPU (memory-builder.html)
- **Dependency Management**: Eliminated external inference servers (Ollama) in favor of browser-native models
- **Sidecar Interface**: Simplified to focus solely on retrieval and search functionality

## [2.1.0] - 2025-12-31 "Daemon Eyes & Passive Observation"

### Added
- **Daemon Eyes**: Implemented "Digital Proprioception". System now observes user screen activity via `sidecar.html` toggle.
- **Vision Pipeline**: Integrated `vision_engine.py` to convert images/screenshots into semantic text memories.
- **Live Context Loop**: Added `POST /v1/vision/screenshot` for non-blocking background context ingestion.
- **Unified Sidecar**: Merged Retrieval and Vision tools into `tools/sidecar.html`.
- **Context UI**: Added `tools/context.html` for simplified read-only context retrieval with scrollable display and one-click copy
- **New Endpoints**: Added bridge endpoints for serving UI and processing vision requests:
    - `GET /sidecar` - Serves the unified control center
    - `GET /context` - Serves the read-only context retrieval UI
    - `POST /v1/vision/ingest` - Handles image upload and VLM processing
    - `POST /v1/vision/screenshot` - Handles background screenshot processing
    - `POST /v1/memory/search` - Implements memory graph search functionality

### Changed
- **Context Strategy**: Shifted from "Manual Copy-Paste" to "Passive Accumulation + Manual Retrieval".
- **Bridge Architecture**: `webgpu_bridge.py` now manages background tasks (FastAPI `BackgroundTasks`) for image processing to prevent UI freezing.
- **UI Workflow**: Unified workflow to browser-based control center, reducing terminal interaction needs

## [2.0.3] - 2025-12-31 "Browser-Based Control Center & VLM Integration"

### Added
- **Vision Engine**: Created `tools/vision_engine.py` for Python-powered image analysis using Ollama backend
- **Browser Control Center**: Implemented `tools/sidecar.html` with dual tabs for context retrieval and vision ingestion
- **Context UI**: Added `tools/context.html` for manual context retrieval with scrollable display and one-click copy
- **New Endpoints**: Added bridge endpoints for serving UI and processing vision requests:
    - `GET /sidecar` - Serves the sidecar dashboard
    - `GET /context` - Serves the context retrieval UI
    - `POST /v1/vision/ingest` - Handles image upload and VLM processing
    - `POST /v1/memory/search` - Implements memory graph search functionality
- **VLM Integration**: Full integration pipeline from image upload → Python VLM → memory graph ingestion

### Changed
- **Bridge Enhancement**: Extended `webgpu_bridge.py` to serve UI files and orchestrate vision processing
- **Memory Search**: Implemented placeholder search functionality with realistic response structure
- **UI Workflow**: Unified workflow to browser-based control center, reducing terminal interaction needs

## [2.0.2] - 2025-12-31 "Test Suite Organization & Pipeline Verification"

### Added
- **Test Directory Structure**: Created dedicated `tests/` directory in project root for all test files
- **Test File Migration**: Moved all test files from `tools/` and `scripts/` to new `tests/` directory:
    - `test_model_loading.py` → `tests/test_model_loading.py`
    - `test_model_availability.py` → `tests/test_model_availability.py`
    - `test_orchestrator.py` → `tests/test_orchestrator.py`
    - `model_test.html` → `tests/model_test.html`
    - `test_gpu_fixes.py` → `tests/test_gpu_fixes.py`
- **Test Configuration Updates**: Updated test files to use correct port (8000 instead of 8080) for current architecture
- **Comprehensive Test Suite**: Enhanced test coverage for model loading, endpoint accessibility, and data pipeline verification

### Changed
- **Project Organization**: Consolidated all test assets into dedicated directory for better maintainability
- **Test Architecture**: Updated test configurations to match current Anchor Core unified architecture (port 8000)

## [2.0.1] - 2025-12-30 "Server Stability & Endpoint Fixes"

### Fixed
- **Server Startup Issues**: Resolved server hanging issues caused by problematic path parameter syntax (`:path`) in route definitions that prevented proper server startup
- **Missing Endpoints**: Added critical missing endpoints (`/v1/models/pull`, `/v1/models/pull/status`, `/v1/gpu/lock`, `/v1/gpu/status`, etc.) that were documented but missing from implementation
- **Endpoint Accessibility**: Verified all documented endpoints are now accessible and responding properly
- **Model Availability**: Improved model availability testing showing that `Qwen2.5-Coder-1.5B-Instruct-q4f16_1-MLC` and `Qwen2.5-7B-Instruct-q4f16_1-MLC` have most files available (missing only `params.json`)

### Architecture Shift
- **Unified Anchor Core**: Consolidated Bridge, File Server, and UI into a single process (`webgpu_bridge.py`) running on **Port 8000**.
- **Single Origin**: Eliminated CORS issues and port confusion. UI, API, and Models are served from the same origin.
- **Protocol**:
    - Brain: `http://localhost:8000/chat.html`
    - Terminal: `http://localhost:8000/terminal.html`
    - API: `http://localhost:8000/v1/...`

### Removed / Archived
- **CLI Bloat**: Deleted `anchor.py` and `sov.py` in favor of web-based `terminal.html` or direct API calls.
- **Legacy Scripts**: Archived `start-bridge.bat`, `start-ghost-shell.bat`, `launch-ghost.ps1`, `hot_reload_gpu.py`, and others to `archive/v2_ghost_shell/`.

### Added
- **start-anchor.bat**: Single-click launcher that starts the Core and the Ghost Engine (Minimized Browser).

## [1.2.4] - 2025-12-29 "Ghost & Shell Architecture"

### Added
- **Ghost & Shell Architecture**: Implemented headless Ghost engine with native Anchor shell for OS integration
- **Auto-Ignition Protocol**: Added auto-start sequence for headless browser with `?headless=true` parameter
- **Anchor Terminal**: Created `tools/anchor.py` for native PowerShell interface with natural language processing
- **Spawn Endpoint**: Added `/v1/system/spawn_shell` to launch native terminals from dashboard
- **Neural Shell Protocol**: Enhanced `/v1/shell/exec` to process natural language to PowerShell commands
- **UTF-8 Encoding Fix**: Added Windows encoding enforcement to prevent Unicode crashes in bridge
- **Minimized Window Approach**: Updated `scripts/launch-ghost.ps1` to use `--start-minimized` for proper GPU access
- **Unified Startup**: Consolidated to single `start-ghost-shell.bat` script launching complete architecture

### Changed
- **Renamed Kernel**: Migrated from `sovereign.js` to `anchor.js` with updated imports across all components
- **Simplified Bridge**: Streamlined `webgpu_bridge.py` with essential functionality only
- **Updated Neural Terminal**: Modified `tools/neural-terminal.html` to use new shell protocol
- **Dashboard Integration**: Added Anchor Shell button to `tools/index.html`
- **Startup Scripts**: Consolidated multiple startup scripts to single unified approach

### Fixed
- **Windows Encoding**: Resolved Unicode encoding crashes with UTF-8 enforcement
- **Bridge Authorization**: Fixed authentication token consistency across components
- **Headless GPU Access**: Resolved WebGPU initialization issues with minimized window approach
- **Model Loading**: Fixed auto-load sequence for Ghost engine with proper model selection
- **Cache Bypass Protocol**: Implemented "Stealth Mode" for browser AI engine by overriding Cache API and modifying static file headers to force browser to treat models as "data in RAM" rather than "persistent storage", bypassing strict security policies.
- **NoCacheStaticFiles**: Custom StaticFiles class with `Cache-Control: no-store` headers to prevent browser cache API usage when serving models through the bridge.
- **Neural Shell Protocol**: Activated "The Hands" (Layer 3) in `webgpu_bridge.py` (`/v1/shell/exec`), allowing the browser to execute system commands on the host.
- **Neural Terminal**: `tools/neural-terminal.html` provides a matrix-style command interface for direct shell access from the browser.
- **Hot Reload Improvement**: Fixed `start-sovereign-console-hotreload.bat` port conflicts and added `/file-mod-time` endpoint to `smart_gpu_bridge.py` for correct frontend reloading.
- **Root Mic (Audio Input)**: Renamed `sovereign-mic.html` to `root-mic.html` and added "Summarize & Clarify" feature using the local Qwen2.5 model.
- **Long-Form Transcription**: Fixed Whisper pipeline to support recordings >30s using chunking and striding.
- **CozoDB Corruption Recovery**: Enhanced error handling for IndexedDB corruption with automatic fallback to in-memory database, manual recovery button, and timeout protection against hanging WASM calls.
- **Bulk CozoDB Import Tool**: Added `tools/prepare_cozo_import.py` to transform `combined_memory.json` into the canonical `relations` payload (`cozo_import_memory.json`) for atomic bulk imports into CozoDB.
- **Import Safety & Verification**: Added recommended import procedure and a post-import verification + backup step to avoid Schema Detachment.
- **WebGPU Bridge**: `webgpu_bridge.py` for proxying OpenAI API requests to browser workers.
- **Chat Worker**: `webgpu-server-chat.html` for running LLMs in the browser.
- **Embed Worker**: `webgpu-server-embed.html` for running embedding models in the browser.
- **Mobile Chat**: `mobile-chat.html` for a lightweight, mobile-friendly UI.
- **Log Viewer**: `log-viewer.html` for real-time server log monitoring.

### Changed
- **Model Loading**: Updated `model-server-chat.html` to use bridge-based model URLs (`http://localhost:8080/models/`) with comprehensive cache-disabling configuration to prevent Cache API errors.
- **Ingestion Defaults**: Recommended batch size increased to 100 to prevent long-running slow writes that can desync CozoDB's in-memory metadata.
- **Git Configuration**: Added `models/` directory to `.gitignore` to prevent committing large binary model files.

---

## [1.2.3] - 2025-12-19 "Snapdragon Optimization"

### Added
- **Qwen3 Support**: Added `Qwen3-4B-Instruct` to the verified model list.
- **Llama 3.2 Support**: Added `Llama-3.2-1B-Instruct` as the recommended lightweight model.
- **Buffer Override**: Implemented `appConfig` overrides to force high-end performance on 256MB GPUs (fixing Adreno throttling).

### Changed
- **Portable Launchers**: All scripts now use `--user-data-dir="%~dp0browser_data"` for fully portable, clean-running instances.
- **Model Config**: Refactored `CreateMLCEngine` initialization to handle both URL-based and ID-based model definitions reliably.

---

## [1.2.2] - 2025-12-18 "Hermes & CozoDB Fixes"

### Fixed
- **Hermes Model Support**: Fixed 404 errors for OpenHermes and NeuralHermes by mapping them to the verified `Mistral-v0.3` WASM library.
- **CozoDB Date Formatting**: Removed `strftime` dependency from WASM queries (causing `no_implementation` errors) and moved date formatting to client-side JavaScript.
- **Drag-and-Drop Import**: Fixed handling of CozoDB `relations` export format in drag-and-drop ingestion.
- **Documentation**: Established `specs/mlc-urls.md` as a registry for verified WASM binaries.

---

## [1.2.1] - 2025-12-15 "DeepSeek & CozoDB Stabilization"

### Fixed
- **CozoDB Initialization**: Resolved `CozoDb.new_from_path is not a function` error by switching to `CozoDb.new_from_indexed_db` for persistent browser storage (IndexedDB backend).
- **WASM Memory Access**: Fixed "memory access out of bounds" error in `sovereign-db-builder.html` and `unified-coda.html` by correctly stringifying JSON parameters passed to `db.run()`.
- **DeepSeek Configuration**: Fixed "Cannot find model record" error in `unified-coda.html` by decoupling the internal model ID from the HuggingFace URL.

### Added
- **Sovereign Hub**: Created `tools/index.html` as a central dashboard for the Console, Builder, and Log Viewer.
- **Log Viewer Upgrade**: Refactored `tools/log-viewer.html` to use `BroadcastChannel` for real-time, polling-free log updates from the console.
- **Expanded File Support**: Updated `sovereign-db-builder.html` to support ingestion of a wider range of code and config files (ts, rs, go, sql, ini, xml, etc.).

## [1.2.0] - 2025-12-15 "Sovereign Architecture"

### Added
- **Sovereign Console**: Created `tools/unified-coda.html`, a standalone WASM-based chat console with local CozoDB (OPFS) and Transformers.js.
- **Sovereign DB Builder**: Created `tools/sovereign-db-builder.html` for ingesting JSON logs into the browser-based database.
- **Model Support**: Expanded `unified-coda.html` to support the full range of MLC-compatible models (Llama 3.2, Qwen 2.5, Gemma 2, etc.).

### Changed
- **Log Management**: Updated backend logging to truncate files at 500KB to prevent disk bloat.

## [1.1.0] - 2025-12-14 "Browser Stability & Bridge Fixes"

### Fixed
- **WebGPU Bridge**: Patched `tools/webgpu_bridge.py` to accept any model name, resolving 503 errors during embedding requests.
- **LLM Client**: Updated `backend/src/llm.py` to correctly identify and use the configured embedding model (`nomic-embed-text-v1.5`).
- **Coda Chat**: Modified `backend/src/recipes/coda_chat.py` to sanitize and truncate `retrieve_memory` outputs. Large JSON payloads were causing `Maximum call stack size exceeded` errors in the browser-based LLM worker.

## [1.0.0] - 2025-12-08 "Infinite Context Pipeline"

### Added
- **Phase 1: Hardware Foundation**: All LLM servers now boot with 65,536 context window and Flash Attention enabled
- **Phase 2: Context Rotation Protocol**: ContextManager automatically rotates context when exceeding 55k tokens
- **Phase 3: Graph-R1 Enhancement**: GraphReasoner now retrieves ContextGist memories for historical continuity
- **ContextGist Nodes**: Neo4j storage for compressed historical context summaries with chronological links
- **Context Shifting Logic**: Intelligent distillation of old content using Distiller agent with gist creation
- **Documentation Structure**: Organized specs/ directories at root, backend, and anchor levels with spec.md, plan.md, tasks.md
- **Infinite Context Pipeline**: Complete end-to-end implementation enabling unlimited context window management

### Changed
- **Upgraded Context Windows**: All start scripts now default to 64k context for infinite work capability
- **Enhanced Memory Architecture**: Neo4j now stores both active memories and ContextGist historical summaries
- **Improved ContextManager**: Added check_and_rotate_context() logic with automatic gist creation and storage
- **Extended GraphReasoner**: Updated retrieval queries to include ContextGist nodes alongside regular memories
- **Optimized Distiller Integration**: Enhanced _chunk_and_distill functionality for context rotation use cases
- **Refined Archivist Agent**: Now coordinates context rotation and gist management operations

### Fixed
- **Context Limit Elimination**: Fixed issue where systems would crash when reaching context limits
- **Memory Continuity**: Resolved problems with historical context access across conversation boundaries
- **Performance Optimization**: Fixed inefficiencies in large context handling with 64k window support
- **Rotation Logic**: Fixed issues with context preservation during rotation cycles

---

## [0.9.0] - 2025-12-07 "Reka & Local Proxy"

### Added
- **Reka Configuration**: Full support for Reka-Flash-3-21B (Q4_K_S) with 16k context, stop tokens, and optimized LLaMa server flags.
- **Local API Proxy**: Added `scripts/local_api_proxy.py` to enforce static API keys for local LLaMa instances (fixes Cline extension "OpenAI API Key" requirement).
- **VS Code Integration**: Added `.vscode/settings.json` template and `VSCODE_CLINE_SETUP.md` for seamless local development.
- **MCP Health**: Added `/health` endpoint to Unified Launcher for better compatibility.

### Fixed
- **MCP Routing**: Resolved duplicate `/mcp` prefix in Unified Launcher routes (`/mcp/tools` is now accessible).
- **LLM Client**: Added `stop` token support to API payloads and local GGUF generation.

## [0.8.0] - 2025-12-06 "Archivist Protocol"

### Added
- **Archivist Ingestion**: Implemented `POST /archivist/ingest` endpoint to accept live data from the browser.
- **Memory Schema**: Enforced **Directive INJ-A1** (`PlaintextMemory`) for immutable "Page-Store" records.
- **Modular DOM Adapters**:
    - `GeminiAdapter`: Clean extraction for Google Gemini.
    - `ChatGPTAdapter`: Clean extraction for ChatGPT.
    - `ClaudeAdapter`: Clean extraction for Claude.ai.
    - `GenericAdapter`: Universal fallback for any webpage.
- **Extension UI**: Added **[Save to Memory]** button to the Side Panel for manual ingestion.

### Fixed
- **Encoding Crash**: Resolved Windows `charmap` error by enforcing `PYTHONIOENCODING='utf-8'`.
- **Server Stability**: Fixed startup crashes caused by `MemoryWeaver` resource contention.

## [0.7.0] - 2025-12-06 "Operation Concrete"

### Added
- **Browser Bridge**: A Chrome Extension (MV3) capable of:
    - **Voice**: Streaming chat interface via Side Panel.
    - **Sight**: Context injection (reading active tab).
    - **Hands**: JavaScript execution on active pages (User-ratified).
- **Backend Architecture**: Migrated from monolithic scripts to **Modular Recipes** (MAX Agentic Cookbook standard).
    - `CodaChatRecipe`: Handles orchestration, context, and tool execution.
- **Persistence**: Side panel now saves chat history to local storage.
- **Markdown Support**: Chat interface renders code blocks and syntax highlighting.

### Changed
- **Identity**: System formally renamed from "Sybil" to **"Coda"**.
- **Documentation**: Adopted `specs/` based documentation policy.

### Fixed
- **Audit Logger**: Patched critical `NameError` in streaming endpoints.
- **Security**: Hardened extension execution via `world: "MAIN"` to bypass strict CSP on some sites.

---

## [0.6.0] - 2025-11-30 "Operation MCP Integrated"

### Added
- **MCP Integration**: Complete integration of MCP server into main ECE Core server
- **Unified Endpoint**: All MCP functionality now available at `/mcp` on main server (port 8000)
- **Memory Tools**: Enhanced MCP tools for memory operations:
    - `add_memory` - Add to Neo4j memory graph
    - `search_memories` - Search memory graph with relationships
    - `get_summaries` - Get session summaries
- **Configuration**: New `mcp_enabled` setting in config.yaml to toggle integration
- **Authentication**: MCP endpoints now inherit main server authentication settings

### Changed
- **Architecture**: MCP server no longer runs as separate process, now integrated into main ECE server
- **Endpoints**: MCP tools now accessed via `/mcp/tools` and `/mcp/call` instead of separate server
- **Deployment**: Simplified deployment - no need to start separate MCP service
- **Resources**: Reduced memory footprint by eliminating duplicate server processes

### Fixed
- **Connection Issues**: Resolved intermittent connection failures between ECE and external MCP server
- **Latency**: Reduced tool call latency by eliminating inter-service communication overhead
- **Synchronization**: Fixed race conditions in concurrent tool executions

---

## [0.5.1] - 2025-11-29 "Memory Weaver Security Audit"

### Added
- **Security Hardening**: Added input validation for all GraphReasoner queries
- **Audit Trail**: Enhanced logging for all automated relationship repairs
- **Circuit Breakers**: Added fail safes for Weaver operations

### Changed
- **Weaver Engine**: Refactored to use parameterized queries, preventing Cypher injection
- **Permission Model**: Strengthened access controls for relationship modification operations

### Fixed
- **Cypher Injection**: Patched vulnerability in Neo4j relationship queries
- **Race Conditions**: Fixed concurrency issues in automated repair operations
- **Resource Exhaustion**: Added limits to prevent DoS via excessive repair requests

---

## [0.5.0] - 2025-11-28 "Memory Weaver (Automated Repair)"

### Added
- **Memory Weaver Engine**: Automated system for detecting and repairing broken relationships in Neo4j
- **Similarity Detection**: Embedding-based relationship discovery for linking related memories
- **Audit System**: Complete traceability for all automated repairs with `auto_commit_run_id`
- **Rollback Capability**: Deterministic reversal of automated changes via `rollback_commits_by_run.py`
- **Scheduler**: Background maintenance tasks for continuous graph integrity

### Changed
- **Graph Maintenance**: Automated relationship repair now runs as background process
- **Quality Assurance**: Enhanced relationship validation with similarity scoring
- **Traceability**: All automated changes now logged with unique run identifiers

### Fixed
- **Orphaned Nodes**: Automatically discovers and connects isolated memories
- **Broken Links**: Repairs missing relationships between related concepts
- **Data Drift**: Corrects inconsistent metadata across related nodes

---

## [0.4.0] - 2025-11-25 "Graph-R1 Implementation"

### Added
- **Graph Reasoner**: Iterative "Think → Query → Retrieve → Rethink" reasoning engine
- **Q-Learning Retrieval**: Reinforcement learning for optimized memory access patterns
- **Markovian Reasoning**: Chunked thinking with state preservation across context shifts
- **Multi-Hop Queries**: Complex graph traversal for answering compound questions
- **Cognitive Agents**: Plugin architecture for specialized reasoning tasks

### Changed
- **Retrieval Method**: Replaced simple vector search with Graph-R1 retrieval
- **Memory Access**: Graph-based traversal now primary method for context assembly
- **Agent Architecture**: Modular cognitive agents for specialized tasks
- **Context Building**: Enhanced context with relationship-aware retrieval

### Fixed
- **Context Relevance**: Improved precision of memory retrieval
- **Chain of Thought**: Better preservation of reasoning pathways
- **Memory Decay**: Reduced loss of historical context in long conversations

---

## [0.3.1] - 2025-11-20 "Security Hardening"

### Added
- **API Authentication**: Token-based authentication for all endpoints
- **Rate Limiting**: Request throttling to prevent abuse
- **Input Sanitization**: Enhanced validation for all user inputs
- **Audit Logging**: Comprehensive logging of all sensitive operations
- **Secure Defaults**: Safe configuration presets for common deployment scenarios

### Changed
- **Security Model**: Implemented zero-trust architecture
- **Credential Handling**: Secure storage and transmission of API keys
- **Access Controls**: Granular permissions for different API endpoints

### Fixed
- **Authentication Bypass**: Patched critical vulnerability in API access
- **Data Exposure**: Resolved information disclosure in error messages
- **Injection Attacks**: Fixed potential SQL injection in Neo4j queries

---

## [0.3.0] - 2025-11-15 "Neo4j Migration Complete"

### Added
- **Neo4j Integration**: Complete migration from SQLite to Neo4j graph database
- **Redis Cache**: Hot cache layer for active session management
- **Graph Schema**: Formal schema definition for memory relationships
- **Migration Tools**: Scripts to migrate existing SQLite data to Neo4j
- **Backup System**: Automated graph backup and restoration procedures

### Changed
- **Storage Architecture**: Tiered storage (Redis hot cache + Neo4j persistent)
- **Query Language**: Cypher queries for graph operations
- **Relationship Modeling**: Graph-based connections between memories
- **Indexing Strategy**: Graph-based indices for faster retrieval

### Fixed
- **Performance**: Significantly improved query performance for complex relationships
- **Scalability**: Better handling of large-scale memory graphs
- **Consistency**: Stronger data integrity with ACID-compliant transactions

---

## [0.2.0] - 2025-10-30 "Cognitive Agents"

### Added
- **Verifier Agent**: Fact-checking via empirical distrust protocol
- **Archivist Agent**: Memory maintenance and staleness detection
- **Distiller Agent**: Content summarization and extraction
- **Agent Framework**: Plugin system for extensible cognitive capabilities
- **Truth Scoring**: Provenance-aware fact-checking with primary source priority

### Changed
- **Memory Hygiene**: Automated maintenance of memory quality
- **Verification Process**: Evidence-based fact-checking system
- **Quality Assurance**: Continuous assessment of memory reliability
- **Maintenance Schedule**: Regular memory grooming operations

### Fixed
- **Hallucinations**: Reduced false information in responses
- **Stale Information**: Automatic detection and updating of outdated memories
- **Data Quality**: Improved content validation and cleaning procedures

---

## [0.1.0] - 2025-09-15 "Initial Architecture"

### Added
- **Core Backend**: Initial ECE_Core with SQLite memory system
- **Anchor Interface**: Terminal interface for user interaction
- **Basic Memory**: Text-based memory storage and retrieval
- **LLM Integration**: Support for various local LLM servers
- **Plugin System**: Extensible tool architecture (UTCP)

### Changed
- **Foundation**: Established core architecture patterns
- **API Design**: Defined RESTful API structure for components

### Fixed
- **Basic Functionality**: Initial implementation of core features