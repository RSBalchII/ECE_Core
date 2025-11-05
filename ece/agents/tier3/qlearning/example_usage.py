"""
Example usage of the QLearningAgent

This script demonstrates how to initialize and use the QLearningAgent
to find optimal paths in a knowledge graph.
"""

import asyncio
import os
from ece.agents.tier3.qlearning.qlearning_agent import QLearningGraphAgent
from ece.agents.tier3.qlearning.neo4j_manager import Neo4jManager


async def main():
    """Main function to demonstrate QLearningAgent usage."""
    print("QLearningAgent Example")
    print("=" * 30)

    # Get Neo4j connection details from environment variables, with defaults for local development
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "ECE_secure_password_2025")

    # Create Neo4j manager
    neo4j_manager = Neo4jManager(neo4j_uri, neo4j_user, neo4j_password)

    # Create QLearning agent
    qlearning_agent = QLearningGraphAgent(
        graph_manager=neo4j_manager,
        config={
            "learning_rate": 0.1,
            "discount_factor": 0.9,
            "epsilon": 0.1,
            "training_interval": 300,  # 5 minutes
        },
    )

    # Example: Find an optimal path between two nodes
    print("Finding optimal path...")
    try:
        paths = await qlearning_agent.find_optimal_path("start_node_id", "end_node_id")
        if paths:
            print(f"Found {len(paths)} path(s):")
            for i, path in enumerate(paths):
                print(
                    f"  Path {i + 1}: {' -> '.join(path.nodes)} (Score: {path.score})"
                )
        else:
            print("No paths found.")
    except Exception as e:
        print(f"Error finding path: {e}")

    # Example: Start continuous training
    print("nStarting continuous training...")
    try:
        await qlearning_agent.start_continuous_training()
        print("Continuous training started.")

        # Let it run for a bit
        await asyncio.sleep(5)

        # Stop continuous training
        await qlearning_agent.stop_continuous_training()
        print("Continuous training stopped.")
    except Exception as e:
        print(f"Error with continuous training: {e}")

    # Example: Get convergence metrics
    print("nConvergence metrics:")
    try:
        metrics = qlearning_agent.get_convergence_metrics()
        for key, value in metrics.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"Error getting convergence metrics: {e}")

    # Example: Synchronize Q-values to graph
    print("nSynchronizing Q-values to graph...")
    try:
        await qlearning_agent.sync_q_values_to_graph()
        print("Q-values synchronized.")
    except Exception as e:
        print(f"Error synchronizing Q-values: {e}")


if __name__ == "__main__":
    asyncio.run(main())
