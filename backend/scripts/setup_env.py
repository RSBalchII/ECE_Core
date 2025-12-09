import os
from pathlib import Path

def setup_env():
    env_path = Path(__file__).parent.parent / ".env"
    
    print("ECE_Core Environment Setup")
    print("==========================")
    
    current_env = {}
    if env_path.exists():
        print(f"Found existing .env at {env_path}")
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    current_env[key] = val
    else:
        print("No .env file found. Creating new one.")

    # LLM Configuration
    print("\n--- LLM Configuration ---")
    print("1. Use Local Llama.cpp Server (Recommended)")
    print("2. Use Local GGUF File")
    print("3. Use OpenAI-compatible API (e.g. LM Studio)")
    
    choice = input("Select option (default 1): ").strip() or "1"
    
    if choice == "1":
        current_env["LLM_API_BASE"] = "http://localhost:8080/v1"
        current_env["LLM_MODEL_NAME"] = "local-model"
    elif choice == "2":
        path = input("Enter full path to GGUF file: ").strip()
        current_env["LLM_MODEL_PATH"] = path
    elif choice == "3":
        base = input("Enter API Base URL (e.g. http://localhost:1234/v1): ").strip()
        current_env["LLM_API_BASE"] = base
        model = input("Enter Model Name: ").strip()
        current_env["LLM_MODEL_NAME"] = model

    # Neo4j Configuration
    print("\n--- Neo4j Configuration ---")
    pw = input("Enter Neo4j Password (default: password): ").strip() or "password"
    current_env["NEO4J_PASSWORD"] = pw
    
    # Write .env
    with open(env_path, "w") as f:
        for key, val in current_env.items():
            f.write(f"{key}={val}\n")
            
    print(f"\n✅ Configuration saved to {env_path}")
    print("You can now run 'python scripts/import_corpus.py' to import your data.")

if __name__ == "__main__":
    setup_env()
