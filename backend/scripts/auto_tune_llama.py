"""
Auto-tune Llama server settings based on GPU VRAM and model file size.
Usage: python auto_tune_llama.py --apply (to write to configs/.env or ece-core/.env)

Heuristics (conservative):
- Default model weight estimate depends on file size in GB, multiplied by fudge factor.
- KV cache formula used: kv_bytes = 2 * n_layers * n_kv_heads * head_dim * ctx * bytes_per_param
- Default head config for 20B: layers=60, kv_heads=8, head_dim=128 (conservative for GQA)
- Compute a recommended ctx size that allows model + kv + overhead <= VRAM * 0.9
- Suggest ubatch = min(2048, ctx), but also keep ubatch >= 512.
- Suggest batch_size logical = 2048.

"""
import argparse
import os
from pathlib import Path
import subprocess
import json


def get_gpu_vram_gb():
    # Try pynvml if available
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        vram = mem.total / (1024 ** 3)
        pynvml.nvmlShutdown()
        return vram
    except Exception:
        # Fallback to nvidia-smi query
        try:
            out = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits']).decode().strip()
            vram = float(out.splitlines()[0]) / 1024.0
            return vram
        except Exception:
            return None


def get_model_filesize_gb(model_path):
    try:
        if not model_path:
            return None
        p = Path(model_path).expanduser()
        if not p.exists():
            return None
        return p.stat().st_size / (1024 ** 3)
    except Exception:
        return None


def kv_cache_gb(ctx, layers=60, kv_heads=8, head_dim=128, bytes_per_param=2):
    # bytes = 2 * n_layers * n_heads * head_dim * ctx * bytes_per_param
    bytes_total = 2 * layers * kv_heads * head_dim * ctx * bytes_per_param
    return bytes_total / (1024 ** 3)


def recommend_settings(vram_gb, model_gb, target_safety=0.9):
    # conservative top buffer: keep 10% as safety by default
    if vram_gb is None:
        return None
    available = vram_gb * target_safety

    # Estimate model_in_vram as model_gb * 1.1 (account for overhead)
    model_est = (model_gb or 0) * 1.1

    # If model_est already exceeds available, recommend reducing context or using partial offload
    if model_est >= available:
        # Not enough space: recommend reducing parallel or using SWAP
        return {
            'model_est_gb': model_est,
            'recommended_ctx': 4096,
            'ubatch': 512,
            'reason': 'model may be too large to fit comfortably in VRAM; use model-specific partial offloading or reduce ctx.'
        }

    remaining = max(available - model_est, 0.1)
    # find largest ctx such that kv_cache_gb(ctx) <= remaining * 0.9
    # Default head/layer configuration for 20B: 60 layers, 8 kv heads, head_dim 128
    layers = 60
    kv_heads = 8
    head_dim = 128
    bytes_per_param = 2

    # Binary search for ctx up to 65536
    low, high = 1024, 65536
    best = low
    while low <= high:
        mid = (low + high) // 2
        kv_gb = kv_cache_gb(mid, layers=layers, kv_heads=kv_heads, head_dim=head_dim, bytes_per_param=bytes_per_param)
        if kv_gb <= remaining:
            best = mid
            low = mid + 1
        else:
            high = mid - 1

    # recommended ubatch: at least 512, up to 2048; higher for larger ctx
    ubatch = 2048 if best >= 8192 else 1024 if best >= 4096 else 512

    return {
        'model_est_gb': round(model_est, 2),
        'vram_gb': round(vram_gb, 2),
        'recommended_ctx': best,
        'recommended_ubatch': ubatch,
        'recommended_batch': 2048,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', type=str, default=os.environ.get('LLM_MODEL_PATH'))
    parser.add_argument('--apply', action='store_true', help='Write recommended settings to ece-core/.env (append)')
    args = parser.parse_args()

    vram = get_gpu_vram_gb()
    model_gb = get_model_filesize_gb(args.model_path)
    rec = recommend_settings(vram, model_gb)

    print('# GPU VRAM (GB):', vram)
    print('# Model size (GB):', model_gb)
    if rec is None:
        print('Could not detect system VRAM; no recommendations made.')
        return
    print('\n# Recommendation:')
    print(json.dumps(rec, indent=2))

    if args.apply:
        env_file = Path('ece-core') / '.env'
        if not env_file.exists():
            print(f'No {env_file} file found to write; skipping apply')
            return
        # Backup
        env_file_bak = env_file.with_suffix('.env.auto_tune.bak')
        env_file.rename(env_file_bak)
        lines = env_file_bak.read_text().splitlines()
        # Append recommendations
        lines.append(f'LLM_CONTEXT_SIZE={rec["recommended_ctx"]}')
        lines.append(f'LLAMA_SERVER_UBATCH_SIZE={rec["recommended_ubatch"]}')
        lines.append(f'LLAMA_SERVER_BATCH_SIZE={rec["recommended_batch"]}')
        lines.append(f'LLM_EMBEDDINGS_DEFAULT_BATCH_SIZE=2')
        lines.append(f'WEAVER_BATCH_SIZE=2')
        lines.append(f'WEAVER_SLEEP_BETWEEN_BATCHES=1.0')
        env_file.write_text('\n'.join(lines))
        print(f'Wrote recommended settings to {env_file}; original backed up to {env_file_bak}')


if __name__ == '__main__':
    main()
