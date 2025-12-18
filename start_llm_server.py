#!/usr/bin/env python3
"""
LLM Server Launcher with Interactive Model Selection

Starts the llama-server with RTX 4090 16GB VRAM optimized settings
and provides interactive model selection from the models/ directory.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path
import platform

def find_models():
    """Find available model files in multiple directories."""
    # Define multiple search directories - including both relative and absolute paths
    model_search_dirs = [
        Path("models").resolve(),  # Default models directory
        Path("../models").resolve(),  # Common user location (where your actual models are)
        Path("../../models").resolve(),  # Another common location
        Path("C:/Users/rsbiiw/Projects/models").resolve(),  # User's actual models directory
        Path("C:/Users/rsbiiw/models").resolve(),  # Alternative common location
        Path("~/models").expanduser().resolve(),  # User home models directory
    ]

    # Also check for environment variable that might specify model path
    env_model_path = os.getenv("MODEL_PATH")
    if env_model_path:
        model_search_dirs.append(Path(env_model_path).resolve())

    # Remove duplicate directories to avoid listing same model multiple times
    unique_dirs = []
    seen_paths = set()
    for models_dir in model_search_dirs:
        if str(models_dir) not in seen_paths:
            unique_dirs.append(models_dir)
            seen_paths.add(str(models_dir))

    # Common model extensions
    extensions = ['.gguf', '.bin', '.safetensors']
    all_candidates = []

    for models_dir in unique_dirs:
        if models_dir.exists():
            print(f"[INFO] Searching in: {models_dir}")
            for ext in extensions:
                try:
                    all_candidates.extend(list(models_dir.rglob(f"*{ext}")))
                except (PermissionError, OSError):
                    print(f"[WARN] Cannot access directory: {models_dir}")
                    continue
        else:
            print(f"[WARN] Models directory not found: {models_dir}")

    # Filter out non-model files that might match extensions and check if files exist
    models = []
    seen_files = set()  # Track absolute paths to avoid duplicates

    for candidate in all_candidates:
        try:
            # Only add if it's a real file (not broken symlink) and doesn't contain skip patterns
            if (candidate.is_file() and candidate.exists() and
                not any(skip in str(candidate).lower() for skip in [
                    'tokenizer', 'config', 'merges', 'vocab', 'special_tokens', 'params'
                ])):
                # Check if file size is valid (not a broken symlink pointing to non-existent file)
                if candidate.stat().st_size > 0:
                    # Use absolute path to avoid duplicates from different search paths
                    abs_path = candidate.resolve()
                    if str(abs_path) not in seen_files:
                        models.append(candidate)
                        seen_files.add(str(abs_path))
        except (OSError, PermissionError):
            continue  # Skip files that cause permission or access issues (like broken symlinks)

    return sorted(models)

def select_model_interactive():
    """Interactive model selection with filtering for RTX 4090 compatible models."""
    models = find_models()
    
    if not models:
        print("[ERROR] No model files found in models/ directory")
        print("[INFO] Expected location: ./models/")
        return None
    
    print(f"\n[INFO] Found {len(models)} model files:")
    print("-" * 60)

    # Filter out files that don't actually exist and show models with basic info
    valid_models = []
    for model in models:
        try:
            if model.exists() and model.is_file():
                valid_models.append(model)
        except:
            continue  # Skip files that cause issues

    # Show valid models with basic info
    for i, model in enumerate(valid_models, 1):
        try:
            size_mb = model.stat().st_size / (1024 * 1024)
            # Determine location: show if it's from local models dir or external
            current_dir = Path('.').resolve()
            model_path = model.resolve()
            if model_path.parts[:len(current_dir.parts)] == current_dir.parts:
                # Model is in local project directory
                location = "local models/"
            else:
                # Model is in an external directory
                location = f"external: {model.parent.name}/"
            print(f"{i:2d}. {model.name}")
            print(f"    Size: {size_mb:.1f} MB | Location: {location}")
        except:
            print(f"{i:2d}. {model.name}")
            print(f"    Size: unknown | Location: {model.parent.name}/")

    if not valid_models:
        print("[ERROR] No valid model files found in models/ directory")
        return None

    models = valid_models  # Use only valid models
    print("-" * 60)
    
    # Filter models by size for RTX 4090 16GB considerations
    print("\n[INFO] For RTX 4090 16GB VRAM, consider these size guidelines:")
    print("   - 20B-25B Q4_K_M/S: ~10-13 GB VRAM")
    print("   - 14B Q4_K_M: ~7-8 GB VRAM") 
    print("   - 7B Q4_K_M: ~3.5-4 GB VRAM")
    print("   - 4B Q4_K_M: ~2-2.5 GB VRAM")
    
    while True:
        try:
            choice = input(f"\nEnter model number (1-{len(models)}) or 'q' to quit: ").strip()
            if choice.lower() == 'q':
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
            else:
                print(f"[ERROR] Please enter a number between 1 and {len(models)}")
        except ValueError:
            print("[ERROR] Please enter a valid number or 'q' to quit")

def find_llama_server():
    """Find llama-server executable."""
    # Common locations and names for llama-server
    possible_paths = [
        # Your actual llama.cpp installation
        "C:/Users/rsbiiw/llama.cpp/build/bin/Release/llama-server.exe",
        # Alternative common locations on your system
        "C:/Users/rsbiiw/llama.cpp/build/bin/llama-server.exe",
        "C:/Users/rsbiiw/llama.cpp/bin/llama-server.exe",
        "../llama.cpp/build/bin/Release/llama-server.exe",
        # Windows
        "llama-server.exe",
        "llama.cpp/server/llama-server.exe",
        "llama.cpp/build/bin/llama-server.exe",
        "C:/Users/rsbiiw/llama.cpp/server/llama-server.exe",
        # Unix-like
        "./llama-server",
        "llama-server",
        "llama.cpp/server/llama-server",
        "llama.cpp/build/bin/llama-server",
    ]

    for path in possible_paths:
        if Path(path).exists():
            print(f"[INFO] Found llama-server at: {Path(path).resolve()}")
            return Path(path).resolve()

    print(f"[ERROR] Could not find llama-server executable in any of these locations:")
    for path in possible_paths:
        print(f"  - {Path(path).resolve()}")
    print("[INFO] Expected at: llama-server.exe (Windows) or ./llama-server (Unix)")
    return None

def get_system_specs():
    """Get system specifications like RAM, VRAM, CPU info."""
    import psutil
    import platform

    specs = {
        'total_ram_gb': round(psutil.virtual_memory().total / (1024**3), 2),
        'available_ram_gb': round(psutil.virtual_memory().available / (1024**3), 2),
        'cpu_count': psutil.cpu_count(),
        'cpu_freq': psutil.cpu_freq().max if psutil.cpu_freq() else 2.0,  # default to 2.0 GHz
        'platform': platform.system(),
        'is_windows': platform.system() == 'Windows'
    }

    # Try to get VRAM info (this is approximate)
    specs['vram_gb'] = 16.0  # Default assumption for typical setup

    return specs

def analyze_model(model_path):
    """Analyze model characteristics based on filename and size."""
    import re
    model_name = model_path.name.lower()
    size_bytes = model_path.stat().st_size
    size_gb = round(size_bytes / (1024**3), 2)

    characteristics = {
        'size_gb': size_gb,
        'is_qwen': 'qwen' in model_name,
        'is_gemma': 'gemma' in model_name or 'gemma3' in model_name,  # More comprehensive Gemma detection
        'is_llama': 'llama' in model_name or 'llm' in model_name,
        'is_moe': 'moe' in model_name or '4x' in model_name or 'california' in model_name,
        'quantization': 'q8' if 'q8' in model_name else 'q4' if 'q4' in model_name else 'f16' if 'f16' in model_name else 'unknown',
        'base_model': 'qwen3' if 'qwen3' in model_name else 'gemma3' if 'gemma' in model_name else 'llama' if 'llama' in model_name else 'unknown'
    }

    return characteristics

def get_optimal_settings(model_char, system_specs):
    """Get optimal settings based on model characteristics and system specs."""
    settings = {}

    # Determine context size based on model size and available RAM
    if model_char['size_gb'] <= 2.0:
        settings['ctx_size'] = 131072  # 128k for small models
    elif model_char['size_gb'] <= 4.0:
        settings['ctx_size'] = 65536   # 64k for 4B models
    elif model_char['size_gb'] <= 7.0:
        settings['ctx_size'] = 32768   # 32k for 7B models
    elif model_char['size_gb'] <= 10.0:
        settings['ctx_size'] = 16384   # 16k for 10B models (like your 4x3 MoE)
    else:
        settings['ctx_size'] = 8192    # 8k for larger models

    # Adjust for available RAM
    available_ram_gb = system_specs['available_ram_gb']
    if available_ram_gb < 8:
        settings['ctx_size'] = max(2048, settings['ctx_size'] // 4)  # Conservative
    elif available_ram_gb < 16:
        settings['ctx_size'] = max(4096, settings['ctx_size'] // 2)  # Moderate
    # If 16GB+ available, keep full context size

    # Determine batch sizes based on model size
    if model_char['size_gb'] <= 4.0:
        settings['batch_size'] = 1024
        settings['ubatch_size'] = 1024
    elif model_char['size_gb'] <= 7.0:
        settings['batch_size'] = 512
        settings['ubatch_size'] = 512
    else:
        settings['batch_size'] = 256
        settings['ubatch_size'] = 256

    # Determine GPU layers based on VRAM
    vram_gb = system_specs['vram_gb']
    if vram_gb >= 16:
        settings['gpu_layers'] = 99  # All layers
    elif vram_gb >= 8:
        settings['gpu_layers'] = 35  # Most layers
    else:
        settings['gpu_layers'] = 20  # Some layers

    # Determine threads based on CPU count
    cpu_count = system_specs['cpu_count']
    settings['threads'] = min(12, max(4, cpu_count - 2))  # Use most but not all cores

    # Model-specific settings
    if model_char.get('is_qwen', False):
        settings['pooling'] = 'cls'
        settings['rope_freq_base'] = 10000
    elif model_char.get('is_gemma', False):
        settings['pooling'] = 'cls'
        settings['rope_freq_base'] = 10000
    elif model_char.get('is_llama', False):
        settings['pooling'] = 'mean'
        settings['rope_freq_base'] = 1000000  # Llama-specific
    else:
        # Default values if model type cannot be determined
        settings['pooling'] = 'cls'
        settings['rope_freq_base'] = 10000

    return settings

def check_flash_attention_support(llama_server_path):
    """Check if the llama-server supports the --fa (flash attention) flag."""
    # Test run with just the --fa flag to see if it's recognized - most reliable method
    try:
        # Use a quick test with just --fa flag to check if it's recognized
        result = subprocess.run([str(llama_server_path), "--fa"],
                              capture_output=True, text=True, timeout=5)
        error_text = result.stderr.lower() if result.stderr else ""
        output_text = result.stdout.lower() if result.stdout else ""

        # If it says "invalid argument", "unknown option", "unrecognized" for --fa, then it's not supported
        full_output = error_text + output_text
        if ("invalid argument" in full_output or
            "unknown" in full_output or
            "unrecognized" in full_output or
            "unrecognized option" in full_output or
            "does not exist" in full_output or
            "error" in full_output):
            return False
        else:
            # If the exit code is non-zero with just --fa, it's likely not supported
            return result.returncode == 0
    except Exception as e:
        # If test fails completely, assume flash attention is not supported
        return False

def start_llm_server(model_path, port=8080):
    """Start llama-server with system-aware optimized settings."""
    llama_server = find_llama_server()
    if not llama_server:
        return False

    print(f"\n[INFO] Analyzing system and model for optimal settings...")
    print(f"   Model: {model_path}")
    print(f"   Port: {port}")
    print(f"   Server: {llama_server}")

    # Get system specs and analyze model
    system_specs = get_system_specs()
    model_char = analyze_model(model_path)

    print(f"   System RAM: {system_specs['total_ram_gb']}GB | Available: {system_specs['available_ram_gb']}GB")
    print(f"   CPU Cores: {system_specs['cpu_count']}")
    print(f"   Model Size: {model_char['size_gb']}GB | Type: {model_char['base_model']}")
    print(f"   Quantization: {model_char['quantization']}")

    # Get optimal settings
    optimal_settings = get_optimal_settings(model_char, system_specs)

    print(f"   Optimized Context Size: {optimal_settings['ctx_size']}")
    print(f"   Optimized Batch Sizes: {optimal_settings['batch_size']}/{optimal_settings['ubatch_size']}")

    # Check for flash attention support
    fa_support = check_flash_attention_support(llama_server)
    print(f"   Flash Attention Support: {'Yes' if fa_support else 'No'}")

    # For infinite context work, we use fixed 64k context
    # But respect the system specs if they indicate limited RAM
    if system_specs['available_ram_gb'] >= 16:
        ctx_size = "65536"  # 64k for systems with sufficient RAM
    elif system_specs['available_ram_gb'] >= 8:
        ctx_size = "32768"  # 32k for systems with moderate RAM
    else:
        ctx_size = "16384"  # 16k for systems with limited RAM

    print(f"   Selected Context Size: {ctx_size} tokens")

    # Build the command with optimal settings
    cmd = [
        str(llama_server),
        "-m", str(model_path),
        "--port", str(port),
        "--ctx-size", ctx_size,      # Fixed for infinite context work capability
        "--n-gpu-layers", str(optimal_settings['gpu_layers']),  # Adjusted based on VRAM
        "--threads", str(optimal_settings['threads']),    # Adjusted based on CPU count
        "--batch-size", str(optimal_settings['batch_size']),  # Adjusted based on model size
        "--ubatch-size", str(optimal_settings['ubatch_size']), # Adjusted based on model size
        "--parallel", "1",          # Single parallel slot (safe default)
        "--mirostat", "2",          # Advanced sampling
        "--temp", "1.0",            # Default temperature
        "--top-p", "0.95",          # Nucleus sampling
        "--cache-type-k", "q8_0",   # Quantized KV cache to save memory
        "--cache-type-v", "q8_0",   # Quantized KV cache to save memory
        "--embeddings",             # Enable embeddings for memory operations
        "--jinja",                  # Enable Jinja template support for tools/function calling
        "--rope-scaling", "linear", # Better handling for contexts
    ]

    # Add rope frequency base if available in settings
    if 'rope_freq_base' in optimal_settings:
        cmd.extend(["--rope-freq-base", str(optimal_settings['rope_freq_base'])])  # Model-specific
    else:
        cmd.extend(["--rope-freq-base", "10000"])  # Default value

    # Add flash attention flag if supported
    if fa_support:
        cmd.append("--fa")          # Flash Attention for better performance

    # Add model-specific pooling
    if 'pooling' in optimal_settings:
        cmd.extend(["--pooling", optimal_settings['pooling']])

    print(f"\n[DEBUG] Command: {' '.join(cmd)}")
    print("\n[INFO] Starting server... (this may take a moment to load the model)")

    # Setup logging
    log_dir = Path("backend/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / "llm_server.log"
    print(f"[INFO] Logging output to: {log_file_path.resolve()}")

    log_file = None
    try:
        # Open log file for appending
        log_file = open(log_file_path, "a", encoding="utf-8")
        
        # Write header to log
        import datetime
        log_file.write(f"\n\n{'='*80}\n")
        log_file.write(f"Starting LLM Server at {datetime.datetime.now().isoformat()}\n")
        log_file.write(f"Model: {model_path}\n")
        log_file.write(f"Command: {' '.join(cmd)}\n")
        log_file.write(f"{'='*80}\n\n")
        log_file.flush()

        # Start the server process, redirecting stdout/stderr to log file
        process = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)

        # Wait for user to stop the server
        print(f"\n[SUCCESS] Server started successfully!")
        print(f"   - API available at: http://localhost:{port}")
        print(f"   - Health check: curl http://localhost:{port}/v1/models")
        print(f"   - Optimized for: {model_char['base_model']} model ({model_char['size_gb']}GB)")
        print(f"   - Logs: {log_file_path}")
        print("\n[INFO] Press Ctrl+C to stop the server")

        # Wait for process to complete (or be interrupted)
        process.wait()

    except KeyboardInterrupt:
        print(f"\n[INFO] Shutting down LLM server...")
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("[SUCCESS] Server stopped")
    finally:
        if log_file:
            log_file.close()

    return True

def main():
    parser = argparse.ArgumentParser(description="LLM Server Launcher (RTX 4090 Optimized)")
    parser.add_argument("--port", type=int, default=8080, help="Port for llama-server (default: 8080)")
    parser.add_argument("--model", type=str, help="Path to model file (skip for interactive selection)")
    parser.add_argument("--list", action="store_true", help="List available models and exit")
    
    args = parser.parse_args()
    
    if args.list:
        models = find_models()
        print(f"Available models ({len(models)} found):")
        for i, model in enumerate(models, 1):
            size_mb = model.stat().st_size / (1024 * 1024)
            print(f"  {i:2d}. {model} ({size_mb:.1f} MB)")
        return
    
    if args.model:
        model_path = Path(args.model)
        if not model_path.exists():
            print(f"[ERROR] Model file not found: {model_path}")
            return
    else:
        model_path = select_model_interactive()
        if not model_path:
            print("[ERROR] No model selected, exiting")
            return
    
    success = start_llm_server(model_path, args.port)
    if not success:
        print("[ERROR] Failed to start LLM server")
        sys.exit(1)

if __name__ == "__main__":
    main()