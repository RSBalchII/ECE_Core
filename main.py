# main.py
# Main entrypoint for the Chimaera External Context Engine (ECE).
# This script initializes and runs the Youtu-agent framework based on the provided configuration.

import yaml
from youtu_agent.agent import Agent

def main():
    """
    Loads the agent configuration, initializes the OrchestraAgent,
    and starts an interactive user session.
    """
    print("🚀 Initializing Chimaera ECE...")

    # Load the master configuration file
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        print("✅ Configuration loaded successfully.")
    except FileNotFoundError:
        print("❌ ERROR: config.yaml not found. Please ensure it is in the root directory.")
        return
    except yaml.YAMLError as e:
        print(f"❌ ERROR: Could not parse config.yaml: {e}")
        return

    # Initialize the main OrchestraAgent using the framework's factory method
    # The framework will handle loading the LLM and tools based on the config.
    try:
        orchestrator = Agent(agent_name="OrchestraAgent", config=config)
        print("✅ OrchestraAgent initialized.")
        print("\n--- Coda D-002 is online. How can I assist you? ---")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize the OrchestraAgent: {e}")
        return

    # Start the interactive loop
    try:
        while True:
            user_input = input("\nArchitect > ")
            if user_input.lower() in ["quit", "exit"]:
                print("\n--- Coda D-002 shutting down. ---")
                break
            
            # The agent's run method handles the entire plan-act loop
            response = orchestrator.run(user_input)
            print(f"\nCoda > {response}")

    except KeyboardInterrupt:
        print("\n\n--- Session interrupted by user. Coda D-002 shutting down. ---")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred during the session: {e}")

if __name__ == "__main__":
    main()