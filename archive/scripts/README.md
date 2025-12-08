# Startup Scripts (Developer & Production)

This folder contains canonical development startup scripts for the Context-Engine project. The scripts in
`scripts/dev/` are the canonical copies used by the repo. For backwards compatibility, there are thin
wrappers in the repo root that call these canonical scripts. Keeping canonical logic here helps with
discoverability and reduces duplication.

Canonical scripts (use these from `scripts/dev`):

- `start-llama-server.bat` - Starts the main LLaMa inference server (Windows)
- `start-llama-server-safe.bat` - Starts LLaMa safe defaults for low OOM risk
- `start-llama-server-safe.sh` - Unix version
- `start-embed-server.bat` - Starts the LLaMa embedding-only server
- `start-embed-server.sh` - Unix version
- `start-openai-stream-proxy.bat` - Windows proxy to shim OpenAI streaming → SSE
- `start-openai-stream-proxy.sh` - Unix-compatible proxy
- `start-ece-core.bat` / `start-ece-core.sh` - Start ECE Core (launcher)
- `start-mcp-server.bat` / `start-mcp-server.sh` - Start the MCP server (optional)
- `start-all-safe.bat` / `start-all-safe.sh` - Start everything safely in the correct order

Wrappers in repo root
---------------------
Root-level scripts are thin wrappers that invoke the canonical dev scripts. This lets tooling and
developers use the existing filenames (`start-llama-server.bat` etc.) while keeping a single,
maintainable canonical copy of each script in this folder.

If you prefer a clean root directory, update your local shell or IDE to use the scripts in
`scripts/dev/` directly.

Archiving policy
----------------
- If a script is no longer needed or is a historical wrapper, it should be placed under `archive/startup-scripts/`.
- To add a script to the canonical set, add it to `scripts/dev/` and then update or replace the root wrapper.

Tips
----
- Always run scripts from the repo root so relative paths resolve correctly.
- Use a Python venv in `ece-core/.venv` and run `pip install -r ece-core/requirements.txt` to get the dependencies.
- On Windows, run the scripts from PowerShell: `.\start-all-safe.bat` etc.

Models & Common Issues
----------------------
- The LLaMa server requires a compiled server executable (eg llama.cpp server) and a model file in GGUF format.
- Set the LLaMa server executable and model path in your environment or `.env` file. Examples (PowerShell):

	$env:LLAMA_SERVER = 'C:\path\to\llama-server.exe'
	$env:MODEL_PATH = 'C:\path\to\models\7B\ggml-model-f16.gguf'

- To install Python dependencies (Windows PowerShell):

	cd 'C:\Users\rsbiiw\Projects\Context-Engine\ece-core'
	if (Test-Path .\.venv\Scripts\Activate) { & .\.venv\Scripts\Activate }
	pip install -r requirements.txt

- Validate the artifact paths before starting the servers; the canonical startup scripts will now perform preflight checks and print helpful tips if something is missing.
- If you need models, use an official model provider/distribution you are licensed to use (e.g., Hugging Face or vendor-provided distribution) and place the GGUF in the models folder or set MODEL_PATH to an accessible location.

Troubleshooting
---------------
- Missing Python packages like `sse_starlette`, `uvicorn` or `PyYAML` can cause the proxy, ECE Core, or config YAML loading to fail. Use the repository venv and install requirements:

	pip install -r requirements.txt

- Test for an installed package inside Python:

	python -c "import sse_starlette; print('sse_starlette', sse_starlette.__version__)"
	python -c "import yaml; print('PyYAML', yaml.__version__)"
	python -c "import uvicorn; print('uvicorn', uvicorn.__version__)"

- If a server starts but you see "failed to open GGUF file", check that `MODEL_PATH` points to a valid GGUF model and that the file exists. The script will now report a helpful error if it cannot find the file.

Archiving outdated wrappers
---------------------------
If your repository root contains legacy thin wrapper scripts (e.g., `start-llama-server.bat`) that simply call canonical scripts in `scripts/dev/`, you can archive them safely to keep the repo root clean.

Use the helpers under `scripts/dev/`:

 - Unix/macOS:
	 ```bash
	 scripts/dev/archive-old-wrappers.sh
	 ```
 - Windows PowerShell:
	 ```pwsh
	 scripts/dev/archive-old-wrappers.ps1
	 ```

The script identifies thin wrappers that call `scripts/dev/start-*` and moves them to `archive/startup-scripts/` with your confirmation.

If you are running this in a CI environment or want to force the archive without prompting, pass `--force` to the PowerShell script or pre-answer `y` to the shell prompt.

Noninteractive / CI mode
------------------------
If you prefer to run the startup in a non-interactive CI environment where no TTY is available, pass `--noninteractive` to the `start-all-safe` script (or set env var `NONINTERACTIVE=1` or `CI=1`) so the script will not attempt interactive model selection and will fail fast if MODEL_PATH is not set.

Verify Models helper
--------------------
If you are unsure which GGUF models are found in your local setup, use the `verify-models` script to list models and their sizes:

 - Unix/macOS: `scripts/dev/verify-models.sh`
 - Windows PowerShell: `scripts/dev/verify-models.ps1`

This is useful to quickly spot if your models folder does not contain the GGUF files expected by `select_model.py` and `start-llama-server`.



