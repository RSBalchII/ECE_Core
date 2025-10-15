import subprocess
import sys
import time
import yaml
from ece.common.windows_memory_limiter import apply_memory_limit
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the agents to run
agents = [
    {"name": "Orchestrator", "path": "ece/agents/tier1/orchestrator/main.py", "port": 8000},
    {"name": "Distiller", "path": "ece/agents/tier3/distiller/distiller_agent.py", "port": 8001},
    {"name": "QLearning", "path": "ece/agents/tier3/qlearning/qlearning_app.py", "port": 8002},
    {"name": "Archivist", "path": "ece/agents/tier3/archivist/archivist_agent.py", "port": 8003},
    {"name": "Injector", "path": "ece/agents/tier3/injector/injector_app.py", "port": 8004},
    {"name": "FileSystem", "path": "ece/agents/tier2/filesystem_agent.py", "port": 8006},
    {"name": "WebSearch", "path": "ece/agents/tier2/web_search_app.py", "port": 8007},
]

def load_config():
    """Loads the application configuration from config.yaml or config_executable.yaml."""
    config_file = "config_executable.yaml" if os.path.exists("config_executable.yaml") else "config.yaml"
    try:
        with open(config_file, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: {config_file} not found. Please ensure the configuration file exists.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing {config_file}: {e}")
        sys.exit(1)

def run_agents(config):
    """
    Runs all the ECE agents as separate processes.
    """
    # Apply memory limit if configured
    if sys.platform == 'win32':
        memory_limit = config.get("system", {}).get("resources", {}).get("memory_limit_mb", 0)
        if memory_limit > 0:
            apply_memory_limit(memory_limit)

    processes = []
    for agent in agents:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            f"{agent['path'].replace('/', '.').replace('.py', '')}:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(agent["port"]),
        ]
        print(f"Starting {agent['name']} on port {agent['port']}...")
        process = subprocess.Popen(command)
        processes.append(process)
        time.sleep(2)  # Give each agent a moment to start up

    print("\nAll agents are running.")
    print("Press Ctrl+C to stop all agents.")

    try:
        # Wait for all processes to complete
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        print("\nStopping all agents...")
        for process in processes:
            process.terminate()
        print("All agents stopped.")

if __name__ == "__main__":
    config = load_config()
    run_agents(config)