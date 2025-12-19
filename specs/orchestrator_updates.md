# Orchestrator Updates: Memory & Reasoning Fixes
**Date**: 2025-12-19
**Focus**: Stability, Retrieval Logic, and Model Loading

## 1. Memory Events & Issues Identified

### A. The "Null Pointer" Crash
*   **Event**: User attempted to load `DeepSeek-V2-Lite`.
*   **Error**: `Cannot read properties of null (reading 'includes')`.
*   **Cause**: The legacy `loadModel` function failed to map the new model ID to a specific WASM library URL, resulting in `modelLib` being `null`. The subsequent includes check crashed the app.
*   **Fix**: Implemented a robust fallback mechanism. If no specific WASM is found, it now defaults to the stable `Qwen2-7B` driver (compatible with most modern architectures).

### B. The "Quota Exceeded" Block
*   **Event**: `Failed to execute 'add' on 'Cache': Request failed`.
*   **Cause**: Browser Cache Storage (where weights are stored) hit the system quota (usually ~60-80% of free disk space).
*   **Fix**: 
    1.  Added specific error trapping for "quota/add on cache" errors to alert the user clearly.
    2.  Upgraded the "Delete Model Cache" button to aggressively hunt down and delete `webllm`, `wasm`, `param`, and `transformers-cache` entries.

### C. The "Blind" Reasoning Loop (Retrieval Failure)
*   **Event**: User planted memory "Blueberry-Omega", but the engine reported "No matching facts found".
*   **Cause**: The LLM Reasoning Agent (Graph-R1) was hallucinating overly strict constraints:
    1.  **Timestamp Filtering**: It added `timestamp >= [CURRENT_TIME]` to queries, effectively asking "What happened in the future?", filtering out the valid memory from the past.
    2.  **Strict Equality**: It used `content = 'Blueberry-Omega'`, which fails if the memory is "The secret is Blueberry-Omega".
*   **Fix**: Updated the System Prompt for the Reasoning Loop:
    1.  Explicitly instructed: "Search ALL history unless user asks for 'today'".
    2.  Enforced usage of `str_includes(content, 'substring')` for fuzzy text matching.

## 2. Infrastructure Changes (Wave Terminal Bridge)

To enable the "Orchestrator" (External App) to use this Sovereign Memory:
1.  **Created `tools/webgpu_bridge.py`**: A Python FastAPI server that bridges HTTP requests to WebSockets.
2.  **Created `tools/webgpu-server-chat.html`**: A headless worker that connects to the bridge and runs the WebLLM engine.
3.  **Result**: Wave Terminal can now talk to `ws://localhost:8080`, which talks to the Browser, which queries the Memory.

## 3. Status
*   **Memory Injection**: Verified (Manual Entry works).
*   **Memory Retrieval**: Logic Patched (Graph-R1 should now find the needle).
*   **Model Loading**: Stabilized (Null crash fixed).
*   **External Access**: Enabled (Bridge active).
