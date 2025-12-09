"""
Generate environment variables for llama servers using `src.config.settings`.
Prints KEY=value lines that can be parsed by Windows batch files.
"""
import json
import os
import sys

# Determine the project root directory (one level up from the scripts directory)
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))

# Add project root to path to ensure modules can be imported
sys.path.insert(0, project_root)

# Change to project root directory to ensure .env file is picked up
original_cwd = os.getcwd()
try:
    os.chdir(project_root)
    from src.config import settings
finally:
    # Restore original working directory
    os.chdir(original_cwd)

# Map our config settings to the environment keys used in the .bat files
OUT = {}

OUT['MODEL'] = getattr(settings, 'llm_model', '') or getattr(settings, 'llm_model_name', '') or getattr(settings, 'llm_model_path', '')
OUT['MODEL_PATH'] = getattr(settings, 'llm_model_path', '')
OUT['CTX_SIZE'] = getattr(settings, 'llm_context_size', '')
OUT['THREADS'] = getattr(settings, 'llm_threads', '')
# Determine ports for API and Embeddings; fall back to config values
try:
    from urllib.parse import urlparse
    api_base = getattr(settings, 'llm_api_base', '') or ''
    if api_base:
        parsed = urlparse(api_base)
        OUT['PORT'] = parsed.port or getattr(settings, 'llama_server_default_port', 8080)
    else:
        OUT['PORT'] = getattr(settings, 'llama_server_default_port', 8080)
    emb_base = getattr(settings, 'llm_embeddings_api_base', '') or ''
    if emb_base:
        parsed_e = urlparse(emb_base)
        OUT['EMBED_PORT'] = parsed_e.port or getattr(settings, 'llama_embed_server_default_port', 8081)
    else:
        OUT['EMBED_PORT'] = getattr(settings, 'llama_embed_server_default_port', 8081)
except Exception:
    OUT['PORT'] = getattr(settings, 'llama_server_default_port', 8080)
    OUT['EMBED_PORT'] = getattr(settings, 'llama_embed_server_default_port', 8081)
# Try to resolve llama-server path in common locations
import os.path

# First, check if there's an explicit setting
if getattr(settings, 'llama_server_exe_path', None):
    OUT['LLAMA_SERVER'] = getattr(settings, 'llama_server_exe_path')
else:
    # Check multiple potential locations for the llama-server executable

    # Option 1: In the ECE_Core project tree (relative to this script)
    project_candidate = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools', 'llama.cpp', 'build', 'bin', 'Release', 'llama-server.exe'))
    if os.path.exists(project_candidate):
        OUT['LLAMA_SERVER'] = project_candidate
    else:
        # Option 2: In the parent directory (common for some setups)
        parent_candidate = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'llama.cpp', 'build', 'bin', 'Release', 'llama-server.exe'))
        if os.path.exists(parent_candidate):
            OUT['LLAMA_SERVER'] = parent_candidate
        else:
            # Option 3: Common global location (tools directory in the main project)
            global_candidate = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools', 'llama.cpp', 'build', 'bin', 'Release', 'llama-server.exe'))
            if os.path.exists(global_candidate):
                OUT['LLAMA_SERVER'] = global_candidate
            else:
                # Option 4: Use the path relative to the repository root
                repo_root_guess = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                llama_candidate = os.path.join(repo_root_guess, 'tools', 'llama.cpp', 'build', 'bin', 'Release', 'llama-server.exe')
                if os.path.exists(llama_candidate):
                    OUT['LLAMA_SERVER'] = llama_candidate
                else:
                    # Check for the actual location shown in the error
                    actual_path = "C:\\Users\\rsbiiw\\Projects\\tools\\llama.cpp\\build\\bin\\Release\\llama-server.exe"
                    if os.path.exists(actual_path):
                        OUT['LLAMA_SERVER'] = actual_path
                    else:
                        # If all else fails, return the path that would be expected to exist and let the batch script handle the error
                        OUT['LLAMA_SERVER'] = llama_candidate
OUT['EMBEDDINGS_FLAG'] = '--embeddings'
OUT['GPU_LAYERS'] = getattr(settings, 'llm_gpu_layers', -1)
OUT['TIMEOUT'] = getattr(settings, 'llm_timeout', 1800)
OUT['N_THREADS'] = getattr(settings, 'llm_threads', 8)
OUT['LLM_API_BASE'] = getattr(settings, 'llm_api_base', '')
OUT['LLM_EMBEDDINGS_API_BASE'] = getattr(settings, 'llm_embeddings_api_base', '')
OUT['LLM_TEMPERATURE'] = getattr(settings, 'llm_temperature', 0.3)
OUT['LLM_TOP_P'] = getattr(settings, 'llm_top_p', 0.85)
OUT['LLM_TIMEOUT'] = getattr(settings, 'llm_timeout', 300)
OUT['LLAMA_ALLOW_SELECT_MODEL'] = getattr(settings, 'llama_allow_select_model', True)
OUT['LLAMA_CONT_BATCHING'] = getattr(settings, 'llama_server_cont_batching', True)
OUT['LLAMA_FLASH_ATTN'] = getattr(settings, 'llama_server_flash_attn', 'auto')
OUT['LLAMA_CACHE_K'] = getattr(settings, 'llama_server_cache_type_k', 'f16')
OUT['LLAMA_CACHE_V'] = getattr(settings, 'llama_server_cache_type_v', 'f16')
OUT['LLAMA_REPEAT_PENALTY'] = getattr(settings, 'llama_server_repeat_penalty', 1.1)
OUT['LLAMA_BATCH'] = getattr(settings, 'llama_server_batch_size', 2048)
# Compute a safe UBATCH: prefer explicit setting, else at minimum the configured llm_context_size

ctx_size_val = None
try:
    ctx_size_val = int(getattr(settings, 'llm_context_size', 0) or 0)
except Exception:
    ctx_size_val = 0

# Optionally apply a UBATCH cap from settings if present to avoid VRAM OOM.
try:
    ubatch_cap = getattr(settings, 'llama_server_ubatch_max', None)
except Exception:
    ubatch_cap = None

configured_ubatch = getattr(settings, 'llama_server_ubatch_size', None)

# If UBATCH isn't configured explicitly, default to a conservative micro-batch size (512)
# This reduces VRAM spikes on consumer GPUs while allowing a larger logical batch size.
if configured_ubatch is None:
    # Default micro-batch size (ubatch) for VRAM stability; set to 2048 to avoid encoder UBATCH asserts
    computed_ubatch = int(getattr(settings, 'llama_server_ubatch_size', 2048) or 2048)
else:
    # If user provided a configured ubatch, use it (but ensure it's at least 512)
    computed_ubatch = max(int(configured_ubatch), 512)

# Apply cap if provided
if ubatch_cap:
    try:
        cap_val = int(ubatch_cap)
        computed_ubatch = min(computed_ubatch, cap_val)
    except Exception:
        pass

OUT['LLAMA_UBATCH'] = computed_ubatch
OUT['LLAMA_PARALLEL'] = getattr(settings, 'llama_server_parallel', 1)
OUT['LLAMA_CACHE_RAM'] = getattr(settings, 'llama_cache_ram', 0)
OUT['LLM_GPU_LAYERS'] = getattr(settings, 'llm_gpu_layers', -1)
OUT['LLM_THREADS'] = getattr(settings, 'llm_threads', 8)

# Print as KEY=value lines for batch parsing
for k, v in OUT.items():
    print(f"{k}={v}")

# Also, output JSON to a file for ease of debugging when being run manually
try:
    with open(os.path.join(os.path.dirname(__file__), 'llama_server_env.json'), 'w') as fh:
        json.dump(OUT, fh, indent=2)
except Exception:
    pass
