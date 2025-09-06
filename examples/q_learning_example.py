"""
Example usage of the QLearningGraphAgent
"""
import asyncio
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.external_context_engine.memory_management.q_learning.q_learning_agent import QLearningGraphAgent
from src.external_context_engine.utils.db_manager import Neo4jManager


async def example_usage():
    """Example of how to use the QLearningGraphAgent"""
    # Initialize Neo4j manager (replace with your actual Neo4j connection details)
    neo4j_manager = Neo4jManager(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password"
    )
    
    try:
        neo4j_manager.connect()
        print("Connected to Neo4j database")
        
        # Initialize QLearningGraphAgent
        config = {
            "learning_rate": 0.1,
            "discount_factor": 0.9,
            "epsilon": 0.1,
            "max_episodes": 1000,
            "q_table_path": "./data/q_table.npy"
        }
        
        agent = QLearningGraphAgent(graph_manager=neo4j_manager, config=config)
        await agent.initialize()
        print("QLearningGraphAgent initialized")
        
        # Example: Find paths between nodes
        start_nodes = [{"name": "NodeA"}]
        end_nodes = [{"name": "NodeB"}]
        
        print("Finding paths...")
        paths = await agent.find_paths(start_nodes, end_nodes, max_hops=5)
        print(f"Found {len(paths)} paths")
        
        # Example: Update Q-values based on a successful path
        path = ["NodeA", "NodeC", "NodeB"]
        reward = 0.8
        print("Updating Q-values...")
        await agent.update_q_values(path, reward)
        print("Q-values updated")
        
        # Example: Train the agent with historical data
        training_data = [
            ("NodeA", "NodeB", 0.8),
            ("NodeB", "NodeC", 0.6),
            ("NodeA", "NodeC", 0.7)
        ]
        print("Training agent...")
        await agent.train(training_data)
        print("Training completed")
        
        # Example: Get convergence metrics
        metrics = agent.get_convergence_metrics()
        print(f"Convergence metrics: {metrics}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        neo4j_manager.disconnect()
        print("Disconnected from Neo4j database")


if __name__ == "__main__":
    asyncio.run(example_usage())