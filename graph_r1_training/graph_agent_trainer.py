<<<<<<< HEAD
import sys









import os
from typing import List, Dict

def list_all_files(base_path: str = os.getcwd()) -> Dict[str, List]:
    """Lists all files in the project directory, including subdirectories."""
    file_paths: List[str] = []

    def traverse(directory):
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                traverse(item_path)  # Recurse into subdirectories
            elif not any(item.startswith('.') or item in ['__pycache__', 'chroma_data', 'venv', 'node_modules', '.vscode', '.idea']):
                file_paths.append(item_path)

    traverse(base_path)
    return {'status': 'success', 'result': file_paths}
# --- Hyperparameters ---
NUM_EPISODES = 500
MAX_STEPS_PER_EPISODE = 20

# Q-Learning Parameters
LEARNING_RATE = 0.1
DISCOUNT_FACTOR = 0.95
EPSILON = 1.0
EPSILON_DECAY = 0.995
MIN_EPSILON = 0.01

def get_reward(graph, current_node):
    """
    Calculates the reward based on node degree (connectedness),
    a proxy for the concept's importance.
    """
    return graph.degree(current_node)

def run_training_simulation(knowledge_graph):
    """Runs the main Q-learning training loop on the provided knowledge graph."""
    if knowledge_graph.number_of_nodes() < 2:
        print("Cannot run training: The knowledge graph has fewer than two nodes.")
        return None

    nodes = list(knowledge_graph.nodes())
    start_node = random.choice(nodes)
    target_node = random.choice(nodes)
    
    while start_node == target_node:
        target_node = random.choice(nodes)

    print(f"\n--- Starting New Training Run ---")
    print(f"Goal: Navigate from '{start_node}' to '{target_node}'")

    agent = QLearningAgent(
        knowledge_graph,
        learning_rate=LEARNING_RATE,
        discount_factor=DISCOUNT_FACTOR,
        epsilon=EPSILON
    )

    for episode in range(NUM_EPISODES):
        agent.reset(start_node=start_node)
        state = agent.current_node

        for step in range(MAX_STEPS_PER_EPISODE):
            action = agent.choose_action()
            if action is None:
                break

            reward = get_reward(knowledge_graph, action)
            next_state = action
            
            if next_state == target_node:
                reward += 500 # Bonus for reaching the target
                done = True
            else:
                done = False

            agent.update_q_table(state, action, reward, next_state)
            state = next_state

            if done:
                break
        
        if agent.epsilon > MIN_EPSILON:
            agent.epsilon *= EPSILON_DECAY

    print(f"Training Run Complete. Final Epsilon: {agent.epsilon:.4f}")
    return agent.q_table

if __name__ == '__main__':
    # Path to the combined text file in the project root
    PATH_TO_TEXT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'combined_text.txt'))

    # 1. Inject the knowledge graph
    injector = GraphInjector(PATH_TO_TEXT)
    our_knowledge_graph = injector.run_pipeline()

    # 2. Train the agent
    final_q_table = run_training_simulation(our_knowledge_graph)

    if final_q_table:
        print("\n--- Final Q-Table (Sample) ---")
        q_table_df = pd.DataFrame.from_dict(final_q_table, orient='index').fillna(0)
=======
import sys
import os
import pandas as pd
import random

# Add the project root for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_r1_training.graph_agent import QLearningAgent
from injector.graph_injector import GraphInjector # Corrected import path

# --- Hyperparameters ---
NUM_EPISODES = 500
MAX_STEPS_PER_EPISODE = 20

# Q-Learning Parameters
LEARNING_RATE = 0.1
DISCOUNT_FACTOR = 0.95
EPSILON = 1.0
EPSILON_DECAY = 0.995
MIN_EPSILON = 0.01

def get_reward(graph, current_node):
    """
    Calculates the reward based on node degree (connectedness),
    a proxy for the concept's importance.
    """
    return graph.degree(current_node)

def run_training_simulation(knowledge_graph):
    """Runs the main Q-learning training loop on the provided knowledge graph."""
    if knowledge_graph.number_of_nodes() < 2:
        print("Cannot run training: The knowledge graph has fewer than two nodes.")
        return None

    nodes = list(knowledge_graph.nodes())
    start_node = random.choice(nodes)
    target_node = random.choice(nodes)
    
    while start_node == target_node:
        target_node = random.choice(nodes)

    print(f"\n--- Starting New Training Run ---")
    print(f"Goal: Navigate from '{start_node}' to '{target_node}'")

    agent = QLearningAgent(
        knowledge_graph,
        learning_rate=LEARNING_RATE,
        discount_factor=DISCOUNT_FACTOR,
        epsilon=EPSILON
    )

    for episode in range(NUM_EPISODES):
        agent.reset(start_node=start_node)
        state = agent.current_node

        for step in range(MAX_STEPS_PER_EPISODE):
            action = agent.choose_action()
            if action is None:
                break

            reward = get_reward(knowledge_graph, action)
            next_state = action
            
            if next_state == target_node:
                reward += 500 # Bonus for reaching the target
                done = True
            else:
                done = False

            agent.update_q_table(state, action, reward, next_state)
            state = next_state

            if done:
                break
        
        if agent.epsilon > MIN_EPSILON:
            agent.epsilon *= EPSILON_DECAY

    print(f"Training Run Complete. Final Epsilon: {agent.epsilon:.4f}")
    return agent.q_table

if __name__ == '__main__':
    # Path to the combined text file in the project root
    PATH_TO_TEXT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'combined_text.txt'))

    # 1. Inject the knowledge graph
    injector = GraphInjector(PATH_TO_TEXT)
    our_knowledge_graph = injector.run_pipeline()

    # 2. Train the agent
    final_q_table = run_training_simulation(our_knowledge_graph)

    if final_q_table:
        print("\n--- Final Q-Table (Sample) ---")
        q_table_df = pd.DataFrame.from_dict(final_q_table, orient='index').fillna(0)
>>>>>>> 66db53d25da8299bd4ab5265ddc01b3d5c822d7d
        print(q_table_df.head(15))