# Root Coda Roadmap (V2.1)

**Status:** Ghost & Shell Architecture Deployed
**Focus:** Hardening, Consolidation, and Hygiene.

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
- [x] **The Ears**: Refactored `root-mic.html` to Root Architecture.
- [x] **The Stomach**: Refactored `sovereign-db-builder.html` to Root Architecture.
- [x] **The Brain**: Refactored `model-server-chat.html` to Root Architecture (Graph-R1 preservation).

## Phase 3: Expansion & Hardening (Completed)
- [x] **Resource Hardening**: Implemented "Consciousness Semaphore" in `sovereign.js`.
- [x] **Documentation Refactor**: Executed "Visual Monolith" strategy.
- [x] **Memory Hygiene**: Implement "Forgetting Curve" in `root-dreamer.html`.
- [x] **Active Memory Persistence**: Enable chat to write back to the Graph.
- [x] **Temporal Awareness**: Ground the model in real-time.
- [x] **Mobile Optimization**: Polish mobile UX for `model-server-chat.html`.

## Phase 4: Ghost & Shell Architecture
- [x] **Phase 1:** "Stealth Mode" Cache Bypass (Completed).
- [x] **Phase 2:** Headless Browser Script (`launch-ghost.ps1`) (Completed).
- [x] **Phase 3:** `sov.py` Native Client Implementation.
- [x] **Phase 4:** Neural Shell Protocol (`/v1/shell/exec` endpoint).
- [x] **Phase 4.5:** Ghost Auto-Ignition (Auto-start with ?headless=true flag).
- [x] **Phase 5:** Native Shell Implementation (Anchor terminal with spawn endpoint).
- [ ] **Phase 7:** Migration to C++ Native Runtime (Removing Chrome entirely).

## Phase 6: Federation
- [ ] **Device Sync**: Sync IndexedDB across devices (Peer-to-Peer).
- [ ] **Local-First Cloud**: Optional encrypted backup.
