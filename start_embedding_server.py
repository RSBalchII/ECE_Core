#!/usr/bin/env python3
"""
Embedding Server Launcher

Starts the llama-server with embedding-specific configuration
using the gemma-300m model automatically.
"""
import os
import sys
import subprocess
from pathlib import Path
import argparse

def find_gemma_model():
    """Find the gemma-300m embedding model."""
    # First look in current directory, then in the script's directory
    script_dir = Path(__file__).parent
    possible_dirs = [
        Path("models"),  # Current directory
        script_dir / "models",  # Script's parent directory
        script_dir.parent / "models",  # Parent of script's directory (if script is in a subdirectory)
    ]

    models_dir = None
    for dir_path in possible_dirs:
        if dir_path.exists():
            models_dir = dir_path
            break

    if models_dir is None:
        print("[ERROR] Models directory not found in current directory or script location")
        return None

    # Look for embedding models, starting with gemma-specific ones
    embedding_files = list(models_dir.rglob("*embed*.gguf"))  # All embedding models
    gemma_files = []  # Gemma embedding models specifically

    # Check for gemma embedding models
    for f in embedding_files:
        if 'gemma' in f.name.lower():
            gemma_files.append(f)

    # If no gemma embedding models found, fall back to any gemma model that might work for embeddings
    if gemma_files:
        return gemma_files[0]  # Return the first gemma embedding model found

    # If no embedding models at all, look for any gemma model that might work
    all_gemma = list(models_dir.rglob("*gemma*.gguf"))
    if all_gemma:
        return all_gemma[0]  # Return the first gemma model found

    print("[ERROR] No gemma embedding model found in models/ directory")
    print("[HELP] Expected files like: gemma-300m.gguf, embeddinggemma*.gguf, etc.")
    print(f"[INFO] Available models in models/: {[f.name for f in models_dir.rglob('*.gguf')]}")
    return None

def find_llama_server():
    """Find llama-server executable for embeddings."""
    # Common locations and names for llama-server - prioritizing the user's specific location
    possible_paths = [
        # Windows - Your specific path based on the listing
        "C:/Users/rsbiiw/llama.cpp/build/bin/Release/llama-server.exe",
        # Updated path with Windows style
        "C:\\Users\\rsbiiw\\llama.cpp\\build\\bin\\Release\\llama-server.exe",
        # Windows - other common locations
        ".\\llama-server.exe",
        "llama-server.exe",
        # Fallback to regular server
        "./llama-server",
        "llama-server",
    ]

    for path in possible_paths:
        if Path(path).exists():
            return Path(path).resolve()

    print("[ERROR] Could not find llama-server executable")
    print("\n[HELP] To install llama.cpp server:")
    print("   1. Clone: git clone https://github.com/ggerganov/llama.cpp")
    print("   2. Build: cd llama.cpp && make server")
    print("   3. Or on Windows: cd llama.cpp && mkdir build && cd build && cmake .. && cmake --build . --config Release")
    print("\n[NOTE] Note: Embedding server is optional. ECE Core and LLM server work without it.")
    return None

def start_embedding_server(model_path, port=8081):
    """Start llama-server in embedding mode."""
    llama_server = find_llama_server()
    if not llama_server:
        return False
    
    print(f"\n[EMBED] Starting Embedding Server with gemma model...")
    print(f"   Model: {model_path}")
    print(f"   Port: {port}")
    print(f"   Server: {llama_server}")
    
    # Embedding-optimized settings
    cmd = [
        str(llama_server),
        "-m", str(model_path),
        "--port", str(port),
        "--ctx-size", "2048",    # Smaller context for embeddings
        "--n-gpu-layers", "99",  # Full GPU offload for RTX 4090
        "--threads", "8",        # Fewer threads since embeddings are less intensive
        "--batch-size", "1024",  # Increased batch size to handle larger inputs
        "--ubatch-size", "512",  # Increased micro-batch for embeddings
        "--parallel", "1",       # Single parallel slot
        "--embedding",           # Enable embedding mode specifically
        "--pooling", "mean",     # Mean pooling for embeddings
        "--rope-freq-base", "10000.0",  # Standard RoPE frequency
    ]
    
    print(f"\n[CMD] Command: {' '.join(cmd)}")
    print("\n[WAIT] Starting embedding server... (this may take a moment)")

    try:
        # Start the server process
        process = subprocess.Popen(cmd)

        # Wait for user to stop the server
        print(f"\n[SUCCESS] Embedding server started successfully!")
        print(f"   - API available at: http://localhost:{port}")
        print(f"   - Test embeddings: curl -X POST http://localhost:{port}/v1/embeddings -H 'Content-Type: application/json' -d '{{\"model\":\"{model_path.name}\",\"input\":[\"test text\"]}}'")
        print("\n[INFO] Press Ctrl+C to stop the server")
        
        # Wait for process to complete (or be interrupted)
        process.wait()
        
    except KeyboardInterrupt:
        print(f"\n[STOP] Shutting down embedding server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print("[DONE] Embedding server stopped")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Embedding Server Launcher (Gemma-300m Auto-Config)")
    parser.add_argument("--port", type=int, default=8081, help="Port for embedding server (default: 8081)")
    parser.add_argument("--model", type=str, help="Path to embedding model (defaults to gemma-300m auto-detect)")

    args = parser.parse_args()

    if args.model:
        model_path = Path(args.model)
        if not model_path.exists():
            print(f"[ERROR] Model file not found: {model_path}")
            return
    else:
        model_path = find_gemma_model()
        if not model_path:
            print("[ERROR] Could not find gemma embedding model, exiting")
            return

    success = start_embedding_server(model_path, args.port)
    if not success:
        print("[ERROR] Failed to start embedding server")
        sys.exit(1)

if __name__ == "__main__":
    main()