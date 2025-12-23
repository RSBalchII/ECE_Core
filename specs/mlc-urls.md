# Verified MLC-LLM Model URLs

**Status:** Registry of verified WebLLM-compatible model URLs.
**Last Updated:** Dec 22, 2025
**Source:** `mlc-ai/web-llm` config and verified HTTP checks.

## Technology: WASM + WebGPU Inference

This project uses **WebLLM** (by MLC-AI) to run Large Language Models directly in the browser.

1.  **Compilation:** Models (Llama 3, Qwen 2.5, etc.) are compiled into **WebAssembly (WASM)** modules (`.wasm`). These modules contain the model's architecture and logic, optimized for execution in a web environment.
2.  **Acceleration:** The WASM module uses the **WebGPU API** to access the user's local GPU. This allows for massive parallelism, enabling 7B+ parameter models to run at interactive speeds (20-100+ tokens/sec) on consumer hardware.
3.  **Zero-Server:** No data leaves the browser. The "Backend" is the user's own GPU.

---

## 1. Verified Models (Ready for Production)

These models have been verified to exist in the `v0_2_80` library and are compatible with the current `web-llm` version.

### 🌟 7B - 8B Class (Recommended)
Balanced performance for reasoning and chat. Requires 6GB+ VRAM.

| Model ID | Details | WASM URL |
| :--- | :--- | :--- |
| `Qwen2.5-7B-Instruct-q4f16_1-MLC` | **Best All-Rounder.** Fast, smart, 32k context. | `https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2.5-7B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm` |
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

---

## 2. Experimental / Pending (WASM Missing)

These models are listed in config but their WASM binaries are not currently hosted in the `v0_2_80` folder. **Do not use until binaries are verified.**

*   `Qwen2.5-14B-Instruct-q4f16_1-MLC` (404 Not Found)
*   `DeepSeek-R1-Distill-Qwen-14B-q4f16_1-MLC` (404 Not Found)
*   `Phi-3.5-vision-instruct-q4f16_1-MLC` (404 Not Found)
*   `Qwen2-VL-7B-Instruct-q4f16_1-MLC` (404 Not Found)

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