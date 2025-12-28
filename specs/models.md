# Verified MLC-LLM Model URLs

**Status:** Registry of verified WebLLM-compatible model URLs.
**Last Updated:** Dec 22, 2025
**Source:** `mlc-ai/web-llm` config and verified HTTP checks.

## Technology: WASM + WebGPU Inference

This project uses **WebLLM** (by MLC-AI) to run Large Language Models directly in the browser.

1.  **Compilation:** Models (Llama 3, Qwen 2.5, etc.) are compiled into **WebAssembly (WASM)** modules (`.wasm`). These modules contain the model's architecture and logic, optimized for execution in a web environment.
2.  **Acceleration:** The WASM module uses the **WebGPU API** to access the user's local GPU. This allows for massive parallelism, enabling 7B+ parameter models to run at interactive speeds (20-100+ tokens/sec) on consumer hardware.
3.  **Zero-Server:** No data leaves the browser. The "Backend" is the user's own GPU.

## Official Model Registry

**CRITICAL REFERENCE:** The definitive list of supported models and their WASM binaries can be found at:
- https://github.com/mlc-ai/web-llm/blob/main/src/config.ts#L293
- This contains the official `prebuiltAppConfig` with verified model configurations

**ADDITIONAL VERIFIED LINKS:**
- https://github.com/mlc-ai/web-llm/blob/main/src/config.ts#L293 - Contains verified MLC model configurations and working WASM URLs

---

## 1. Verified Models (Ready for Production)

These models have been verified to exist in the `v0_2_80` library and are compatible with the current `web-llm` version.

### 🌟 7B - 8B Class (Recommended)
Balanced performance for reasoning and chat. Requires 6GB+ VRAM.

| Model ID | Details | WASM URL |
| :--- | :--- | :--- |
| `Qwen2.5-7B-Instruct-q4f16_1-MLC` | **Best All-Rounder.** Fast, smart, 32k context. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-7B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Llama-3.1-8B-Instruct-q4f32_1-MLC` | **Meta's Latest.** Strong reasoning. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-3_1-8B-Instruct-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `Llama-3-8B-Instruct-q4f32_1-MLC` | Llama 3 Base. Reliable. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-3-8B-Instruct-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `DeepSeek-R1-Distill-Qwen-7B-q4f16_1-MLC` | **Reasoning Specialist.** | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-7B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` (Uses Qwen2 base) |

### 🚀 High Performance (Small)
Fastest start times. Works on most laptops/integrated graphics.

| Model ID | Details | WASM URL |
| :--- | :--- | :--- |
| `Phi-3.5-mini-instruct-q4f16_1-MLC` | **Microsoft Phi.** 3.8B params. Very smart for size. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Phi-3.5-mini-instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen2.5-1.5B-Instruct-q4f16_1-MLC` | **Ultra-Lite.** 1.5B params. Blazing fast. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-1.5B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `SmolLM2-1.7B-Instruct-q4f16_1-MLC` | Efficient 1.7B model. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/SmolLM2-1.7B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` |

### 🌟 Gemma Models (Google)
Lightweight and efficient models from Google.

| Model ID | Details | WASM URL |
| :--- | :--- | :--- |
| `gemma-2-9b-it-q4f16_1-MLC` | **Gemma 2 9B.** High performance text generation. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/gemma-2-9b-it-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `gemma-2-9b-it-q4f32_1-MLC` | **Gemma 2 9B.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/gemma-2-9b-it-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `gemma-2-2b-it-q4f16_1-MLC` | **Gemma 2 2B.** Lightweight option. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/gemma-2-2b-it-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `gemma-2-2b-it-q4f32_1-MLC` | **Gemma 2 2B.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/gemma-2-2b-it-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `gemma-3-1b-it-q4f16_1-MLC` | **Gemma 3 1B.** Latest generation small model. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/gemma-3-1b-it-q4f16_1-ctx4k_cs1k-webgpu.wasm` |

### 👁️ Vision Models (Multimodal)
Models that can process both text and images.

| Model ID | Details | WASM URL |
| :--- | :--- | :--- |
| `Phi-3.5-vision-instruct-q4f16_1-MLC` | **Microsoft Phi Vision.** 4.2B params, multimodal. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Phi-3.5-vision-instruct-q4f16_1-ctx4k_cs2k-webgpu.wasm` |
| `Phi-3.5-vision-instruct-q4f32_1-MLC` | **Microsoft Phi Vision.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Phi-3.5-vision-instruct-q4f32_1-ctx4k_cs2k-webgpu.wasm` |

### 🚀 Larger Models (For High VRAM Systems)
Models for systems with 12GB+ VRAM like RTX 4090.

| Model ID | Details | WASM URL |
| :--- | :--- | :--- |
| `Llama-2-13b-chat-hf-q4f16_1-MLC` | **Llama 2 13B.** For high-end systems. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-2-13b-chat-hf-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen3-8B-q4f16_1-MLC` | **Qwen 3 8B.** Latest generation. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen3-8B-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen3-8B-q4f32_1-MLC` | **Qwen 3 8B.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen3-8B-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen3-4B-q4f16_1-MLC` | **Qwen 3 4B.** Balanced performance. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen3-4B-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen3-4B-q4f32_1-MLC` | **Qwen 3 4B.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen3-4B-q4f32_1-ctx4k_cs1k-webgpu.wasm` |

### 🚀 Smaller Models (For Low VRAM Systems)
Models optimized for systems with limited VRAM like the XPS 13.

| Model ID | Details | WASM URL |
| :--- | :--- | :--- |
| `Qwen2-0.5B-Instruct-q4f16_1-MLC` | **Ultra-Lightweight.** 0.5B params. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-0.5B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen2-0.5B-Instruct-q4f32_1-MLC` | **Ultra-Lightweight.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-0.5B-Instruct-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen3-0.6B-q4f16_1-MLC` | **Qwen 3 Tiny.** 0.6B params. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen3-0.6B-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen3-0.6B-q4f32_1-MLC` | **Qwen 3 Tiny.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen3-0.6B-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen3-1.7B-q4f16_1-MLC` | **Qwen 3 Small.** 1.7B params. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen3-1.7B-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Qwen3-1.7B-q4f32_1-MLC` | **Qwen 3 Small.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen3-1.7B-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `Llama-3.2-1B-Instruct-q4f16_1-MLC` | **Llama 3.2 1B.** Efficient small model. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-3.2-1B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Llama-3.2-1B-Instruct-q4f32_1-MLC` | **Llama 3.2 1B.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-3.2-1B-Instruct-q4f32_1-ctx4k_cs1k-webgpu.wasm` |
| `Llama-3.2-3B-Instruct-q4f16_1-MLC` | **Llama 3.2 3B.** Balanced small model. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-3.2-3B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
| `Llama-3.2-3B-Instruct-q4f32_1-MLC` | **Llama 3.2 3B.** Higher precision variant. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Llama-3.2-3B-Instruct-q4f32_1-ctx4k_cs1k-webgpu.wasm` |

---

## 2. Known Issues / Missing Binaries

These models are listed in the official config but their WASM binaries are not currently hosted in the `v0_2_80` folder. **Avoid using these until binaries are available.**

*   `Qwen2.5-14B-Instruct-q4f16_1-MLC` (404 Not Found) - **Known Issue**
*   `DeepSeek-R1-Distill-Qwen-14B-q4f16_1-MLC` (404 Not Found) - **Known Issue**
*   `Qwen2-VL-7B-Instruct-q4f16_1-MLC` (404 Not Found)
*   `gemma-3-2b-it-q4f16_1-MLC` (404 Not Found) - **Note: No Gemma 3 2B available, only 1B exists**
*   `gemma-3-12b-it-q4f16_1-MLC` (404 Not Found) - **Note: No Gemma 3 12B available in current library**

## 3. Verified Working Models (Recommended)

Based on the official config at the GitHub link above, these models are confirmed to have working WASM binaries:

### High Performance (7B-8B Range)
*   `Qwen2.5-7B-Instruct-q4f16_1-MLC` - Verified working
*   `Llama-3.1-8B-Instruct-q4f32_1-MLC` - Verified working
*   `Phi-3.5-mini-instruct-q4f16_1-MLC` - Verified working
*   `gemma-2-9b-it-q4f16_1-MLC` - Verified working
*   `Qwen3-8B-q4f16_1-MLC` - Verified working

### Lightweight Options (1.5B and below)
*   `Qwen2.5-1.5B-Instruct-q4f16_1-MLC` - Verified working
*   `Qwen2-0.5B-Instruct-q4f16_1-MLC` - Verified working
*   `Llama-3.2-1B-Instruct-q4f16_1-MLC` - Verified working
*   `SmolLM2-1.7B-Instruct-q4f16_1-MLC` - Verified working

### Vision Models
*   `Phi-3.5-vision-instruct-q4f16_1-MLC` - Verified working

### 💻 Code Specialists
*   `Qwen2.5-Coder-1.5B-Instruct-q4f16_1-MLC` - **Best for Neural Terminal.** Fast & Smart.
*   `Qwen2.5-Coder-7B-Instruct-q4f16_1-MLC` - Verified working

---

## 3. URL Construction Logic

If you need to construct a URL manually:

```javascript
const libBase = "https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/";
const version = "v0_2_80"; // Check src/config.ts for 'modelVersion'
const modelSpecificName = "Qwen2.5-7B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm";

const fullUrl = `${libBase}${version}/${modelSpecificName}`;
```

**Note:** The `modelSpecificName` often differs slightly from the Hugging Face repo name (e.g., `Llama-3_1` vs `Llama-3.1` or `Qwen2` base for `DeepSeek`). Always check `mlc_config.ts` mapping.