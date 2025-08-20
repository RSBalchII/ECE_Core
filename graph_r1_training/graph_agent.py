import random
import numpy as np
import networkx as nx

class QLearningAgent:
    """
    An agent that uses Q-learning to navigate a NetworkX graph.
    """
    def __init__(self, graph: nx.Graph, learning_rate=0.1, discount_factor=0.9, epsilon=1.0):
        """
        Initializes the Q-learning agent.
        """
        self.graph = graph
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.q_table = self._initialize_q_table()
        self.current_node = None

    def _initialize_q_table(self):
        """Initializes the Q-table with zeros for all state-action pairs."""
        q_table = {}
        for node in self.graph.nodes():
            # For an undirected graph, neighbors are the possible actions.
            q_table[node] = {neighbor: 0 for neighbor in self.graph.neighbors(node)}
        return q_table

    def choose_action(self):
        """
        Chooses an action using an epsilon-greedy strategy.
        """
        possible_actions = list(self.graph.neighbors(self.current_node)) # Changed to .neighbors()
        if not possible_actions:
            return None # Dead end

        if random.uniform(0, 1) < self.epsilon:
            return random.choice(possible_actions)  # Explore
        else:
            q_values = self.q_table.get(self.current_node, {})
            # Handle cases where a node might have no outgoing q_values yet
            if not q_values:
                return random.choice(possible_actions)
            return max(q_values, key=q_values.get) # Exploit

    def update_q_table(self, state, action, reward, next_state):
        """
        Updates the Q-value for a given state-action pair using the Bellman equation.
        """
        # Get the old Q-value, defaulting to 0 if it doesn't exist.
        old_value = self.q_table.get(state, {}).get(action, 0)

        # Get the maximum future Q-value from the next state.
        # If the next_state is a terminal node or has no actions, this is 0.
        if not self.q_table.get(next_state) or not self.q_table[next_state]:
            next_max = 0 # Terminal node or dead end
        else:
            next_max = max(self.q_table[next_state].values())

        # The core Q-learning formula
        new_value = (1 - self.lr) * old_value + self.lr * (reward + self.gamma * next_max)
        
        # Update the table
        # Ensure the state exists in the q_table before updating
        if state not in self.q_table:
            self.q_table[state] = {}
        self.q_table[state][action] = new_value

    def reset(self, start_node='A'):
        """Resets the agent's position."""
        self.current_node = start_node