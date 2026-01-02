# Tools Changelog

## [2.4.0] - 2026-01-01 "Anchor Lite Refactor"
### Changed
- Renamed `chat.html` to `ghost.html` (Headless Engine).
- Refactored `context.html` to be the primary Search Dashboard.
### Removed
- Archived `db_builder.html`, `memory-builder.html`, `mobile-chat.html`.
- Removed auto-loading of WebLLM to save resources.


## [Unreleased] - 2025-12-26

### Added
- **On-Demand Model Serving**: `model-server-chat.html` now checks `http://localhost:8080/models/{id}` before loading. If missing, it triggers a download via the Bridge.
- **Quota Bypass**: Using `useIndexedDBCache: false` for large models to bypass browser storage limits, relying on the Bridge's local file server instead.

### Fixed
- **Model ID Mismatch**: Fixed logic in `loadModel` where the `mlc-ai/` prefix was being aggressively stripped, causing config lookups to fail.
- **UI Progress**: Added real-time progress bars for server-side model downloads.

 - 2025-12-23

### Added
- **Orchestrator Model:** New `orchestrator.py` tool to programmatically interact with the MLC Bridge from Python.
- **Health Endpoint:** Added `/health` to `webgpu_bridge.py` for extension connectivity checks.
- **Audit Whitelist:** Added `/audit/server-logs` to auth whitelist in Bridge to fix Log Viewer 401 errors.

### Changed
- **Bridge Port:** Moved standard bridge port from `8000` to `8080` to avoid conflicts with `http.server`.
- **Launch Scripts:** Updated `start-sovereign-console.bat` and `launch-chromium-d3d12.bat` to respect new port `8080` and correct paths.
- **Root Dreamer:**
  - Robustified `init()` to handle non-Error objects during crash.
  - Improved JSON parsing to strip markdown code blocks before parsing.
  - Added strict engine readiness check to `dreamLoop` to prevent race conditions.
- **Root Console:**
  - Added "High Performance (Small)" models (Qwen 2.5 1.5B, TinyLlama) to the dropdown.
  - Updated JS mapper to handle new small model paths.
  - Fixed crash in `executeR1Loop` where `genErr.message` could be undefined.

### Fixed
- **WebGPU Crash:** Mitigated `DXGI_ERROR_DEVICE_REMOVED` by advising single-tab usage and providing smaller model options for constrained profiles.
- **Extension Connection:** Fixed CORS and Port mismatch preventing the Chrome Extension from connecting to the Bridge.
