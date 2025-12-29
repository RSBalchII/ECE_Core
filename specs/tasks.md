# Context-Engine Implementation Tasks

## Current Work Queue (Ghost & Shell Architecture)

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

### Phase 4.1: The Neural Shell (Active) 🚧
**Objective:** Decouple Intelligence (Chat) from Agency (Terminal).
- [x] **Phase 1:** "Stealth Mode" Cache Bypass (Completed).
- [x] **Phase 2:** Headless Browser Script (`launch-ghost.ps1`) (Completed).
- [x] **Phase 3:** `sov.py` Native Client Implementation.
- [x] **Phase 3.5:** Ghost Auto-Ignition (Headless auto-start with ?headless=true flag).
- [ ] **Phase 4:** Migration to C++ Native Runtime (Removing Chrome entirely).
- [ ] **Bridge Repair**: Debug and stabilize `extension-bridge` connectivity.
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

## Backlog
- [ ] **Federation Protocol**: P2P sync.
- [ ] **Android App**: Wrapper for Root Coda.