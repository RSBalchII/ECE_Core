import random

class GraphAgent:
    """
    A simple agent that can navigate a NetworkX graph.
    """
    def __init__(self, graph, start_node='A'):
        """
        Initializes the agent on the graph.

        Args:
            graph (nx.DiGraph): The knowledge graph to navigate.
            start_node (str): The node where the agent begins.
        """
        self.graph = graph
        self.current_node = start_node

    def get_possible_actions(self):
        """
        Returns a list of possible nodes to move to from the current node.
        """
        return list(self.graph.successors(self.current_node))

    def take_action(self):
        """
        Takes a random action by moving to a random successor node.
        """
        possible_actions = self.get_possible_actions()
        if not possible_actions:
            # If at a dead end, do nothing (or reset, for a more complex scenario)
            return self.current_node

        next_node = random.choice(possible_actions)
        self.current_node = next_node
        return self.current_node

    def reset(self, start_node='A'):
        """
        Resets the agent's position to the start node.
        """
        self.current_node = start_node