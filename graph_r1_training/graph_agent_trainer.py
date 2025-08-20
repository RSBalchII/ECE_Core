from graph_environment import create_simple_knowledge_graph
from graph_agent import GraphAgent

# --- Hyperparameters ---
NUM_EPISODES = 1000
MAX_STEPS_PER_EPISODE = 10
TARGET_NODE = 'D'

def get_reward(current_node):
    """
    Calculates the reward based on the agent's current position.
    """
    if current_node == TARGET_NODE:
        return 100  # High reward for reaching the target
    else:
        return -1   # Small penalty for each step taken

def run_training_simulation():
    """
    Runs the main training loop for the graph agent.
    """
    # 1. Initialize Environment and Agent
    knowledge_graph = create_simple_knowledge_graph()
    agent = GraphAgent(knowledge_graph, start_node='A')

    # 2. Main Training Loop
    for episode in range(NUM_EPISODES):
        agent.reset()
        total_reward = 0

        print(f"--- Episode {episode + 1}/{NUM_EPISODES} ---")

        for step in range(MAX_STEPS_PER_EPISODE):
            current_position = agent.current_node
            
            # 3. Agent takes an action
            next_position = agent.take_action()

            # 4. Get reward for the action
            reward = get_reward(next_position)
            total_reward += reward

            print(f"Step {step + 1}: Moved from {current_position} to {next_position}. Reward: {reward}")

            # 5. Check for terminal state
            if next_position == TARGET_NODE:
                print("Target reached!")
                break
        
        print(f"Episode {episode + 1} finished. Total Reward: {total_reward}n")

if __name__ == '__main__':
    run_training_simulation()