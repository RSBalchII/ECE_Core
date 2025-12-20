# Sovereign Coda Roadmap (V2)

**Status:** Execution Phase (Browser-Native Pivot)
**Focus:** Stability, Model Expansion, Context Injection.

## Phase 1: Foundation (Completed)
- [x] Pivot to WebLLM/WebGPU stack.
- [x] Implement CozoDB (WASM) for memory.
- [x] Create core HTML tools (`model-server-chat`, `sovereign-db-builder`, `log-viewer`).

## Phase 2: Stabilization (Current)
- [x] Fix Model Loading (Quota/VRAM config).
- [x] Add 14B Model Support (Qwen2.5, DeepSeek-R1).
- [x] UI Modernization (Collapsible, Resizable).
- [x] Clean Dependencies (Remove Python backend, fix scripts).
- [x] **Snapdragon Optimization**: Implemented Buffer Override (256MB) and Portable Profiles.

## Phase 3: Context Injection (Next)
- [ ] **Context Injection Debugging**: Ensure loaded context is actually used by the model.
- [ ] **Extension Integration**: Re-verify Chrome Extension bridge.
- [ ] **Hybrid RAG**: Optimize vector + graph retrieval.

## Phase 4: Expansion
- [ ] **Agentic Capabilities**: Re-introduce Verifier/Distiller logic in JS.
- [/] **Mobile Optimization**: Iterate on `model-server-chat.html` mobile UX.
