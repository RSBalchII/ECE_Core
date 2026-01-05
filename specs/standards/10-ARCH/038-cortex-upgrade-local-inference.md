# Standard 038: Cortex Upgrade (Local Inference)

**Status:** Active | **Category:** ARCH | **Authority:** LLM-Enforced

## 1. What Happened
The system required a transition from browser-based WebGPU inference to a stable, headless Node.js-native inference engine to support background tasks like "Dreaming" (self-organization) and CLI-based chat.

## 2. The Cost
- **3 hours** debugging ESM/CJS interop issues with `node-llama-cpp`.
- **2 hours** resolving native binary loading errors in compiled `pkg` environments.
- **1 hour** fixing `contextSequence` null errors in LlamaChatSession initialization.

## 3. The Rule
1. **Dynamic Imports**: Always use `await import('node-llama-cpp')` for the Llama library to maintain compatibility between CommonJS and ESM.
2. **Model Discovery**: Models are loaded from `MODELS_DIR`, which resolves to `../../models` (parent of the project root) by default. This allows team members to share a centralized model repository.
3. **Initialization Flow**:
   - Call `getLlama()` first.
   - Use `llama.loadModel()` with an absolute path.
   - Create a `context` from the model.
   - Initialize `LlamaChatSession` with `contextSequence: context.getSequence()`.
4. **Headless First**: Inference must run without requiring a browser or GPU-accelerated display context.

---
*Verified by Cortex Upgrade Team.*
