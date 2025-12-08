"""
Interactive Model Selector for llama-server
Simple TUI to choose which model to load
"""

import sys
from pathlib import Path
import argparse


def list_models(models_dir: Path):
    """List all GGUF models in directory"""
    models = sorted(models_dir.glob("*.gguf"))
    return models


def list_models_from_both_dirs():
    """List all GGUF models from both local and parent models directories"""
    all_models = {}

    # Look in current directory first (standard location)
    models_dir_current = Path("models")
    if models_dir_current.exists():
        for model in list_models(models_dir_current):
            all_models[model.name.lower()] = model

    # Also look in parent directory
    models_dir_parent = Path("..") / "models"
    if models_dir_parent.exists():
        for model in list_models(models_dir_parent):
            all_models[model.name.lower()] = model

    # Look in directory relative to script location
    models_dir_script = Path(__file__).parent / "models"
    if models_dir_script != models_dir_current and models_dir_script.exists():
        for model in list_models(models_dir_script):
            all_models[model.name.lower()] = model

    # Return sorted list of unique models based on their names
    return sorted(all_models.values(), key=lambda x: x.name.lower())


def display_models(models):
    """Display models with numbers"""
    print("\n" + "=" * 60)
    print("  llama.cpp Model Selector")
    print("=" * 60)
    print()

    if not models:
        print("❌ No GGUF models found in models/ directory")
        return None

    print("Available models:")
    print()

    for i, model in enumerate(models, 1):
        # Get file size in GB
        size_gb = model.stat().st_size / (1024**3)
        # Shorten name for display
        name = model.stem
        if len(name) > 50:
            name = name[:47] + "..."

        print(f"  [{i}] {name}")
        print(f"      Size: {size_gb:.2f} GB")
        print()

    return models


def get_model_config(model_path: Path):
    """Determine optimal settings based on model name and i9-13900HX specs"""
    name = model_path.stem.lower()

    # Get model file size in GB
    size_gb = model_path.stat().st_size / (1024**3)

    # i9-13900HX: 24 cores (8 P-cores + 16 E-cores), 64GB RAM optimal
    # RTX 4090 16GB VRAM laptop edition
    # Default settings optimized for this hardware
    config = {
        "ctx_size": 8192,
        "threads": 24,  # Use all cores for max performance
        "gpu_layers": -1,  # Full GPU offload for RTX 4090 16GB VRAM
        "description": "Standard configuration",
    }

    # Estimate VRAM usage for full offload (rough approximation for Q4_K_M)
    estimated_vram_gb = size_gb * 1.1
    if estimated_vram_gb > 16:
        # Assume ~80 layers for large models, calculate partial offload
        total_layers = 80
        config["gpu_layers"] = int((16 / estimated_vram_gb) * total_layers)
        config["description"] += (
            f" (partial GPU offload: {config['gpu_layers']} layers)"
        )

    # Model-specific optimizations for RTX 4090 16GB VRAM and i9-13900HX
    if "gemma3" in name or "gemma-3" in name:
        config["ctx_size"] = 16384
        config["threads"] = 24
        config["description"] = "Gemma-3 optimized (4B efficient, 16k context)"
    elif "qwen3" in name and "4b" in name:
        config["ctx_size"] = 32768
        config["threads"] = 24
        config["description"] = "Qwen3 4B native context"
    elif "qwen2.5" in name and "3b" in name:
        config["ctx_size"] = 32768
        config["threads"] = 24
        config["description"] = "Qwen2.5-VL 3B optimized"
    elif "qwen3" in name and "8b" in name:
        config["ctx_size"] = 32768
        config["threads"] = 24
        config["description"] = "Qwen3 8B extended"
    elif "qwen" in name:
        config["ctx_size"] = 32768
        config["threads"] = 24
        config["description"] = "Qwen extended context"
    elif "deepseek" in name and "14b" in name:
        config["ctx_size"] = 16384
        config["threads"] = 24
        config["description"] = "DeepSeek-R1 14B optimized"
    elif "deepseek" in name:
        config["ctx_size"] = 16384
        config["threads"] = 24
        config["description"] = "DeepSeek optimized"
    elif "nemotron" in name:
        config["ctx_size"] = 16384
        config["threads"] = 24
        config["description"] = "Nemotron 8B optimized"
    elif "granite" in name and "4" in name:
        config["ctx_size"] = 16384
        config["threads"] = 24
        config["description"] = "Granite 4.0 optimized"
    elif "granite" in name:
        config["ctx_size"] = 8192
        config["threads"] = 24
        config["description"] = "Granite default"
    elif "moe" in name:
        config["ctx_size"] = 16384
        config["threads"] = 24
        config["description"] = "MoE 24B balanced"
        # For MoE models, adjust GPU layers if large
        if size_gb > 10:
            config["gpu_layers"] = 60  # Higher for MoE
            config["description"] += (
                f" (partial GPU offload: {config['gpu_layers']} layers)"
            )
    elif "exaone" in name:
        config["ctx_size"] = 16384
        config["threads"] = 24
        config["description"] = "EXAONE 7.8B optimized"

    return config


def main():
    # Look for models directory in multiple possible locations
    models_dir = None

    # Try current directory first (standard location)
    models_dir_current = Path("models")
    if models_dir_current.exists():
        models_dir = models_dir_current
    else:
        # Try parent directory (where models are located in your setup)
        models_dir_parent = Path("..") / "models"
        if models_dir_parent.exists():
            models_dir = models_dir_parent
        else:
            # Try relative to project root (common case)
            models_dir_abs = Path(__file__).parent / "models"
            if models_dir_abs.exists():
                models_dir = models_dir_abs
            else:
                models_dir = models_dir_current  # Use original for error message

    if not models_dir or not models_dir.exists():
        print(f"❌ Models directory not found: {models_dir}")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Select model and provide port to display/write to temp file.")
    parser.add_argument("--port", type=int, default=8080, help="Port to display and write to config (default: 8080)")
    parser.add_argument("--for-embeddings", action="store_true", default=False, help="Only show/select models that look like embedding models (model names containing 'embed' or 'embedding')")
    args, _ = parser.parse_known_args()

    port = args.port
    for_embeddings = args.for_embeddings

    models = list_models_from_both_dirs()
    if for_embeddings:
        print("⚠️  Showing all models for embeddings. Select an appropriate embedding model.")
        # Removed filtering to show all models - user knows which models are which

    displayed_models = display_models(models)

    if not displayed_models:
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Select model and provide port to display/write to temp file.")
    parser.add_argument("--port", type=int, default=8080, help="Port to display and write to config (default: 8080)")
    args, _ = parser.parse_known_args()

    port = args.port

    # Get user selection
    while True:
        try:
            choice = input(f"Select model [1-{len(models)}] or 'q' to quit: ").strip()

            if choice.lower() == "q":
                print("\n✅ Cancelled")
                sys.exit(0)

            index = int(choice) - 1
            if 0 <= index < len(models):
                selected_model = models[index]
                break
            else:
                print(f"❌ Please enter a number between 1 and {len(models)}")
        except ValueError:
            print("❌ Invalid input. Enter a number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n\n✅ Cancelled")
            sys.exit(0)

    # Get optimal config
    config = get_model_config(selected_model)

    # Display selection
    print("\n" + "=" * 60)
    print("  Selected Model Configuration")
    print("=" * 60)
    print(f"\n  Model: {selected_model.name}")
    print(f"  Context Size: {config['ctx_size']} tokens")
    print(f"  Threads: {config['threads']}")
    print(
        f"  GPU Layers: {config['gpu_layers']} ({'all' if config['gpu_layers'] == -1 else 'partial'})"
    )
    print(f"  Config: {config['description']}")
    print(f"  Port: {port}")
    print("\n" + "=" * 60)
    print()

    # Write to temp file for batch script to read
    with open("selected_model.tmp", "w") as f:
        realpath = selected_model.resolve()
        f.write(f"MODEL={realpath}\n")
        f.write(f"MODEL_PATH={realpath}\n")
        f.write(f"CTX_SIZE={config['ctx_size']}\n")
        f.write(f"THREADS={config['threads']}\n")
        f.write(f"GPU_LAYERS={config['gpu_layers']}\n")
        f.write(f"PORT={port}\n")

    print("✅ Model configuration saved")
    # If user explicitly requested embeddings-only mode, confirm the selected model looks embedding-capable
    if for_embeddings:
        name = selected_model.stem.lower()
        if 'embed' not in name and 'embedding' not in name:
            print("\n⚠️  Selected model does not look like an embedding-capable model. The /v1/embeddings endpoint may return errors or not be supported.")
            cont = input("Continue starting server with this model? [y/N]: ").strip().lower()
            if cont != 'y':
                print('\n✅ Cancelled')
                sys.exit(1)
    print("\nPress Enter to start llama-server...")
    input()


if __name__ == "__main__":
    main()
