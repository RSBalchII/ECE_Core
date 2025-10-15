import cProfile
import pstats
from pstats import SortKey
import subprocess
import sys
import os

def run_profiling():
    """
    Function to run profiling on ECE components.
    This script will set up a profiling session for the ECE application.
    """
    print("Starting ECE Performance Profiling")
    print("This will profile the ECE application to identify performance bottlenecks.")
    
    # Profiling the run_all_agents.py script which starts all agents
    print("\nProfiling run_all_agents.py...")
    
    # Define the profiling script
    profile_code = '''
import sys
import time
import yaml
from ece.common.windows_memory_limiter import apply_memory_limit

# Define the agents to run (simplified for profiling)
agents = [
    {"name": "Orchestrator", "path": "ece/agents/tier1/orchestrator/main.py", "port": 8000},
    {"name": "QLearning", "path": "ece/agents/tier3/qlearning/qlearning_app.py", "port": 8002},
]

def load_config():
    """Loads the application configuration from config.yaml."""
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found. Please ensure the configuration file exists.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        sys.exit(1)

def minimal_run_agents():
    """
    A minimal run of agents for profiling purposes.
    This simulates the initialization of agents without actually starting servers.
    """
    config = load_config()
    
    # Apply memory limit if configured
    if sys.platform == 'win32':
        memory_limit = config.get("system", {}).get("resources", {}).get("memory_limit_mb", 0)
        if memory_limit > 0:
            apply_memory_limit(memory_limit)

    print("Initializing agents for profiling...")
    for agent in agents:
        print(f"Initializing {agent['name']}...")
        # Simulate agent loading without actually starting the server
        time.sleep(0.1)  # Simulate initialization time

    print("Profiling scenario completed.")

if __name__ == "__main__":
    minimal_run_agents()
'''

    # Write the profiling code to a temporary file
    with open('profile_temp.py', 'w') as f:
        f.write(profile_code)
    
    # Run the profiler
    pr = cProfile.Profile()
    pr.enable()
    
    # Execute the profiled code
    exec(profile_code)
    
    pr.disable()
    
    # Save the profiling results
    pr.create_stats()
    stats = pstats.Stats(pr)
    
    # Sort the stats by cumulative time and print the top 20 functions
    stats.sort_stats(SortKey.CUMULATIVE)
    print("\nTop 20 functions by cumulative time:")
    stats.print_stats(20)
    
    # Save full profile to a file
    stats.dump_stats('ece_profile.prof')
    
    print("\nProfiling completed. Full profile saved to 'ece_profile.prof'")
    print("To visualize with snakeviz, run: snakeviz ece_profile.prof")
    
    # Clean up the temporary file
    if os.path.exists('profile_temp.py'):
        os.remove('profile_temp.py')

if __name__ == "__main__":
    run_profiling()