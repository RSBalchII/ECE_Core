# Verified MLC Model Registry

**Status:** Living Document
**Purpose:** Centralize trusted, verified URLs for MLC-LLM models and WASM libraries to prevent cache errors and guessing games.

## Protocol for Adding
1. **Verify** the URL returns 200 OK (use `curl -I`).
2. **Test** the model loads in `model-server-chat.html` (or equivalent).
3. **Commit** the entry here.

---

## Verified Models

### Hermes Family (Users Favorites)

| Model Name | HuggingFace ID | WASM Library URL | Status |
| :--- | :--- | :--- | :--- |
| **Hermes-3-Llama-3.2-3B** | `mlc-ai/Hermes-3-Llama-3.2-3B-q4f16_1-MLC` | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-3.2-3B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` | ✅ **VERIFIED** |
| **OpenHermes-2.5** | `mlc-ai/OpenHermes-2.5-Mistral-7B-q4f16_1-MLC` | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Mistral-7B-Instruct-v0.3-q4f16_1-ctx4k_cs1k-webgpu.wasm` | ✅ **VERIFIED** (via v0.3 engine) |
| **NeuralHermes-2.5** | `mlc-ai/NeuralHermes-2.5-Mistral-7B-q3f16_1-MLC` | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Mistral-7B-Instruct-v0.3-q3f16_1-ctx4k_cs1k-webgpu.wasm` | ✅ **VERIFIED** (via v0.3 engine) |
| **Hermes-2-Pro-Mistral** | `mlc-ai/Hermes-2-Pro-Mistral-7B-q4f16_1-MLC` | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Mistral-7B-Instruct-v0.3-q4f16_1-ctx4k_cs1k-webgpu.wasm` | ✅ **VERIFIED** (via v0.3 engine) |

### Standard MLC Models

| Model Name | HuggingFace ID | WASM Library URL | Status |
| :--- | :--- | :--- | :--- |
| **Llama-3.2-3B-Instruct** | `mlc-ai/Llama-3.2-3B-Instruct-q4f16_1-MLC` | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-3.2-3B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` | ✅ **VERIFIED** |
| **DeepSeek-R1-Distill-Qwen** | `mlc-ai/DeepSeek-R1-Distill-Qwen-7B-q4f16_1-MLC` | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-7B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` | ✅ **VERIFIED** |

### 14B Models (High-End)

| Model Name | HuggingFace ID | WASM Library URL | Status |
| :--- | :--- | :--- | :--- |
| **Qwen 2.5 14B Instruct** | `mlc-ai/Qwen2.5-14B-Instruct-q4f16_1-MLC` | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2.5-14B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` | ✅ **VERIFIED** |
| **DeepSeek R1 Distill 14B** | `mlc-ai/DeepSeek-R1-Distill-Qwen-14B-q4f16_1-MLC` | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2.5-14B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` | ✅ **VERIFIED** (Shared WASM) |
