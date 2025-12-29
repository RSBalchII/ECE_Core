# Sovereign Architecture V2: The Ghost & The Shell

## 1. Overview
Architecture V2 decouples the **Interface** from the **Inference Engine**. 
Instead of a monolithic "Chat UI" inside a browser, the system splits into a background service (Ghost) and a lightweight client (Shell).

## 2. Component A: The Ghost (Headless Engine)
The Ghost is a background process responsible solely for loading the LLM into VRAM and exposing an API.

* **Current Implementation:** Headless Chromium (`launch-ghost.ps1`).
* **Future Implementation:** C++ Native Binary (`neural-ghost.exe`) using Dawn/WebGPU.
* **Responsibility:**
    * Manage WebGPU Context.
    * Load Weights (MLC-LLM).
    * Serve `localhost:8080/v1/chat/completions`.
    * **Stealth Mode:** Uses `NoCacheStaticFiles` to treat models as RAM-only data, bypassing browser storage quotas.

## 3. Component B: The Shell (Native Client)
The Shell is the user interface, residing in the user's native terminal environment (PowerShell, Bash, etc.).

* **Implementation:** Python Client (`tools/sov.py`).
* **Responsibility:**
    * Capture user input (`stdin`).
    * Send JSON payload to The Ghost.
    * Render streamed response to `stdout`.
    * Execute system commands (Agency).

## 4. The Data Flow
1.  **User:** Types `sov "List large files"` in PowerShell.
2.  **Shell:** Sends POST request to `localhost:8080`.
3.  **Bridge:** Forwards request to Headless Browser (Ghost) via Websocket/Fetch.
4.  **Ghost:** Runs inference on RTX 4090 via WebGPU.
5.  **Ghost:** Returns tokens -> Bridge -> Shell.
6.  **Shell:** Displays output or executes `Get-ChildItem` command.

## 5. Roadmap
- [x] **Phase 1:** "Stealth Mode" Cache Bypass (Completed).
- [x] **Phase 2:** Headless Browser Script (Completed).
- [x] **Phase 3:** `sov.py` Native Client Implementation.
- [x] **Phase 4:** Neural Shell Protocol (`/v1/shell/exec` endpoint).
- [x] **Phase 4.5:** Ghost Auto-Ignition (Auto-start with ?headless=true flag).
- [x] **Phase 5:** Native Shell Implementation (Anchor terminal with spawn endpoint).
- [ ] **Phase 6:** Migration to C++ Native Runtime (Removing Chrome entirely).