# Context-Engine Implementation Tasks

## Current Work Queue (Root Architecture)

### Completed - Root Refactor ✅
- [x] **Kernel**: Implement `tools/modules/sovereign.js`.
- [x] **Mic**: Refactor `sovereign-mic.html` to use Kernel.
- [x] **Builder**: Refactor `sovereign-db-builder.html` to use Kernel.
- [x] **Console**: Refactor `model-server-chat.html` to use Kernel (Graph-R1).
- [x] **Docs**: Update all specs to reflect Root Architecture.

### Completed - Hardware Optimization 🐉
- [x] **WebGPU Buffer Optimization**: Implemented 256MB override for Adreno GPUs.
- [x] **Model Profiles**: Added Lite, Mid, High, Ultra profiles.
- [x] **Crash Prevention**: Context clamping for constrained drivers.
- [x] **Mobile Optimization**: Service Worker (`llm-worker.js`) for non-blocking inference.

## Phase 3: The Subconscious (Completed) ✅
- [x] **Root Dreamer**: Created `tools/root-dreamer.html` for background memory consolidation.
- [x] **Ingestion Refinement**: Upgraded `read_all.py` to produce LLM-legible YAML.
- [x] **Root Architecture Docs**: Finalized terminology (Sovereign -> Root).

### Active Development - Expansion
- [ ] **Agentic Tools**: Port Verifier/Distiller logic to `tools/modules/agents.js`.
- [ ] **Multimodal**: Add image support to Builder (drag-and-drop embedding).
- [ ] **Voice Output**: Add TTS to Console.

## Phase 4: The Specialist Array
- [ ] **Dataset Generation**: Samsung TRM / Distillation.
- [ ] **Unsloth Training Pipeline**: RTX 4090 based fine-tuning.
- [ ] **Model Merging**: FrankenMoE construction.

## Backlog
- [ ] **Federation Protocol**: P2P sync.
- [ ] **Android App**: Wrapper for Root Coda.
