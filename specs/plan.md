# Root Coda Roadmap (V2.0)

**Status:** Root Architecture Deployed
**Focus:** Expansion, Agentic Capabilities, Multimodal.

## Phase 1: Foundation (Completed)
- [x] Pivot to WebLLM/WebGPU stack.
- [x] Implement CozoDB (WASM) for memory.
- [x] Create core HTML tools (`model-server-chat`, `sovereign-db-builder`, `log-viewer`).

## Phase 2: Stabilization (Completed)
- [x] Fix Model Loading (Quota/VRAM config).
- [x] Add 14B Model Support (Qwen2.5, DeepSeek-R1).
- [x] **Snapdragon Optimization**: Implemented Buffer Override (256MB).

## Phase 2.5: Root Refactor (Completed)
- [x] **Kernel Implementation**: Created `sovereign.js` (Unified Logger, State, Hardware).
- [x] **The Ears**: Refactored `sovereign-mic.html` to Root Architecture.
- [x] **The Stomach**: Refactored `sovereign-db-builder.html` to Root Architecture.
- [x] **The Brain**: Refactored `model-server-chat.html` to Root Architecture (Graph-R1 preservation).

## Phase 3: Expansion (Current)
- [ ] **Agentic Capabilities**: Re-introduce Verifier/Distiller logic in JS.
- [x] **Active Memory Persistence**: Enable chat to write back to the Graph.
- [x] **Temporal Awareness**: Ground the model in real-time.
- [ ] **Mobile Optimization**: Polish mobile UX for `model-server-chat.html`.
- [ ] **Hybrid RAG**: Optimize vector + graph retrieval weighting.

## Phase 4: Federation
- [ ] **Device Sync**: Sync IndexedDB across devices (Peer-to-Peer).
- [ ] **Local-First Cloud**: Optional encrypted backup.