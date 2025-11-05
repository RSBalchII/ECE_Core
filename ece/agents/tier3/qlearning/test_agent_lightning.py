#!/usr/bin/env python3
"""
Test script for Agent Lightning integration with QLearningAgent
"""

import asyncio
import sys
import os

# Add the project root to the path so we can import the agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from qlearning_agent import QLearningGraphAgent


class MockGraphManager:
    """Mock implementation of a graph manager for testing"""

    def connect(self):
        print("MockGraphManager: Connected to graph")

    def find_nodes_by_keywords(self, keywords):
        """Mock implementation that returns some test nodes"""
        nodes = []
        for i, keyword in enumerate(keywords):
            nodes.append(
                {
                    "id": f"node_{i}",
                    "name": keyword,
                    "properties": {"type": "TestConcept", "relevance": 1.0},
                }
            )
        return nodes

    def get_neighbors(self, node_id):
        """Mock implementation that returns some test neighbors"""
        # Return a few neighboring nodes for testing
        neighbors = []
        for i in range(1, 4):  # Each node has 3 neighbors
            neighbor_id = f"{node_id}_neighbor_{i}"
            neighbors.append(
                {"to_node": neighbor_id, "relationship_type": "RELATED_TO"}
            )
        return neighbors

    def sync_q_values_to_graph(self, q_table):
        """Mock implementation for syncing Q-values"""
        print(f"MockGraphManager: Syncing {len(q_table)} states to graph")


async def main():
    print("Testing Agent Lightning integration with QLearningAgent...")

    # Create a mock graph manager
    mock_graph_manager = MockGraphManager()

    # Create the QLearningAgent with the mock graph manager
    agent = QLearningGraphAgent(
        graph_manager=mock_graph_manager,
        config={"learning_rate": 0.1, "discount_factor": 0.9, "epsilon": 0.1},
    )

    print("\n1. Testing find_optimal_path method...")
    keywords = ["test", "keyword", "example"]
    result = await agent.find_optimal_path(keywords, max_tokens=50000)
    print(f"Found {len(result)} paths")

    print("\n2. Testing Q-value updates...")
    if result:
        # Use the first path for testing updates
        path = result[0]
        await agent.update_q_values(path, reward=0.5)
        print("Q-values updated successfully")

    print("\n3. Testing pathfinding...")
    path_result = await agent._q_learning_pathfinding(
        "start_node", "end_node", max_steps=5
    )
    print(
        f"Pathfinding result: path length {path_result.length}, score {path_result.score}"
    )

    print("\n4. Testing performance metrics...")
    metrics = await agent.get_performance_metrics()
    print(f"Performance metrics collected: {list(metrics.keys())}")

    print("\n5. Testing parameter optimization...")
    dummy_performance_data = [
        {"avg_reward": 0.3, "avg_path_length": 5, "avg_convergence_steps": 50},
        {"avg_reward": 0.7, "avg_path_length": 7, "avg_convergence_steps": 75},
    ]
    optimized_params = await agent.optimize_learning_parameters(dummy_performance_data)
    print(f"Optimized parameters: {optimized_params}")

    print("\nTest completed successfully!")
    print("Agent Lightning events should have been emitted during execution.")


if __name__ == "__main__":
    asyncio.run(main())
