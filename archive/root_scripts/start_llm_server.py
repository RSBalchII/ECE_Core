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
        Path("../models").resolve(),  # Common user location
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
                all_candidates.extend(list(models_dir.rglob(f"*{ext}")))
        else:
            print(f"[WARN] Models directory not found: {models_dir}")

    # Filter out non-model files that might match extensions and check if files exist
    models = []
    seen_files = set()  # Track absolute paths to avoid duplicates

    for candidate in all_candidates:
        try:
            # Only add if it's a real file (not broken symlink) and doesn't contain skip patterns
            if (candidate.is_file() and
                not any(skip in str(candidate).lower() for skip in [
                    'tokenizer', 'config', 'merges', 'vocab', 'special_tokens', 'params'
                ])):
                # Use absolute path to avoid duplicates from different search paths
                abs_path = candidate.resolve()
                if str(abs_path) not in seen_files:
                    models.append(candidate)
                    seen_files.add(str(abs_path))
        except:
            continue  # Skip files that cause permission or access issues

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

def start_llm_server(model_path, port=8080):
    """Start llama-server with RTX 4090 optimized settings."""
    llama_server = find_llama_server()
    if not llama_server:
        return False
    
    print(f"\n[INFO] Starting LLM Server with RTX 4090 16GB VRAM optimized settings...")
    print(f"   Model: {model_path}")
    print(f"   Port: {port}")
    print(f"   Server: {llama_server}")
    
    # RTX 4090 16GB VRAM optimized settings
    cmd = [
        str(llama_server),
        "-m", str(model_path),
        "--port", str(port),
        "--ctx-size", "16384",  # 16k context for reasoning chains
        "--n-gpu-layers", "99",  # Force full GPU offload for RTX 4090
        "--threads", "12",       # CPU threads
        "--batch-size", "2048",  # Large logical batch
        "--ubatch-size", "2048", # Physical micro-batch (tuned for stability)
        "--parallel", "1",       # Single parallel slot for 4090 16GB
        "--mirostat", "2",       # Advanced sampling for Reka-style models
        "--temp", "1.0",         # Temperature for reasoning models
        "--cache-type-k", "f16", # KV cache type for RTX 4090
        "--cache-type-v", "f16", # KV cache type for RTX 4090
        "--embeddings",          # Enable embeddings for memory operations
        "--jinja"                # Enable Jinja template support for tools/function calling
    ]
    
    print(f"\n[DEBUG] Command: {' '.join(cmd)}")
    print("\n[INFO] Starting server... (this may take a moment to load the model)")
    
    try:
        # Start the server process
        process = subprocess.Popen(cmd)
        
        # Wait for user to stop the server
        print(f"\n[SUCCESS] Server started successfully!")
        print(f"   - API available at: http://localhost:{port}")
        print(f"   - Health check: curl http://localhost:{port}/v1/models")
        print("\n[INFO] Press Ctrl+C to stop the server")
        
        # Wait for process to complete (or be interrupted)
        process.wait()
        
    except KeyboardInterrupt:
        print(f"\n[INFO] Shutting down LLM server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print("[SUCCESS] Server stopped")
    
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