# Starting Llama Servers with ECE_Core

You can start llama.cpp-based LLM servers for both inference and embeddings via the scripts in the ECE_Core project.

The `start-llama-server.bat` and `start-embed-server.bat` scripts live in the repo root (`./start-llama-server.bat` and `./start-embed-server.bat`).

How it works:
- `scripts/generate_llama_env.py` reads `src.config.settings` and prints environment variables.
- The batch scripts call the helper to load configuration values from `.env` or environment, and use them to start `llama-server.exe` with appropriate flags (context, threads, GPU layers, etc.).
- For interactive model selection, the scripts call `select_model.py`; if the helper supplied `MODEL`, it will use this directly.

Instructions:
1. Set configuration values in `.env` (for example `LLM_MODEL_PATH`, `LLM_CONTEXT_SIZE`, `LLM_THREADS`, `LLM_GPU_LAYERS`, `LLM_EMBEDDINGS_*`, `LLAMA_SERVER_EXE_PATH`, etc.).
2. Start the API server:
   - Open a PowerShell window in the `ECE_Core` folder and run:

```powershell
.\start-llama-server.bat
```

3. Start the Embeddings server:

```powershell
.\start-embed-server.bat
```

Tip: You can also specify a different set of values using environment variables directly or via a custom `.env` file, and you can override the model selection interactively with `select_model.py` if needed.

Batching guidance (GPU/UBATCH) ☝️
--------------------------------
If you serve many small requests concurrently, we recommend keeping continuous batching enabled (it improves throughput). However, ensure that the `UBATCH` (physical batch size) is large enough to fit typical requests, and also small enough to avoid OOM on your GPU.

For NVIDIA RTX 4090 (16 GB VRAM) laptops, a reasonable starting point is to set:

```env
LLAMA_SERVER_UBATCH_MAX=8192
LLAMA_BATCH=2048
LLAMA_PARALLEL=1
LLAMA_CONT_BATCHING=True
```

Adjust `LLAMA_SERVER_UBATCH_MAX` up or down depending on model size:
- Small embedding models (e.g., 300M): you can often set a higher UBATCH.
- Larger models (4B+): start conservative (4096 or 2048) and raise if the load stays stable.

Use `python scripts/generate_llama_env.py` to dump settings and confirm the final `LLAMA_UBATCH` value prior to starting the server. This helper respects `LLAMA_SERVER_UBATCH_MAX` and will cap the computed UBATCH accordingly.

Pre-flight token validation 📐
---------------------------------
ECE_Core includes a pre-flight validation in the API layer that checks the size of the assembled prompt (in tokens) against the configured `LLAMA_SERVER_UBATCH_SIZE` micro-batch. If the prompt tokens exceed the UBATCH the service returns an HTTP 400 response advising the user to reduce the context size or increase `LLAMA_SERVER_UBATCH_SIZE`. This prevents a llama.cpp GGML assertion (encoder requires n_ubatch >= n_tokens) and reduces 500 Internal Server Errors under heavy load.

Debugging:

Auto-tuning helper 🚀
---------------------
ECE_Core ships with `scripts/auto_tune_llama.py` which can recommend `LLM_CONTEXT_SIZE`, `LLAMA_SERVER_UBATCH_SIZE`, and `LLAMA_SERVER_BATCH_SIZE` based on detected GPU VRAM and model file size. Run it with `python scripts/auto_tune_llama.py` to print recommended settings or `python scripts/auto_tune_llama.py --apply` to append conservative recommendations to `ece-core/.env` (backing up the original). This can be helpful when swapping models on limited VRAM machines like the RTX 4090.
