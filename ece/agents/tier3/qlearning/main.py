"""
Main entry point for the QLearning Agent
"""

import os
import sys
import asyncio

# Add the qlearning agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from qlearning_agent import QLearningGraphAgent
from neo4j_manager import Neo4jManager


def main():
    """Main function to demonstrate the QLearning Agent."""
    # Get Neo4j connection details from environment variables, with defaults for local development
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "ECE_secure_password_2025")

    # Create Neo4j manager
    neo4j_manager = Neo4jManager(neo4j_uri, neo4j_user, neo4j_password)

    # Create an instance of the QLearning agent
    qlearning_agent = QLearningGraphAgent(
        graph_manager=neo4j_manager,
        config={"learning_rate": 0.1, "discount_factor": 0.9, "epsilon": 0.1},
    )

    # Example usage
    print("QLearning Agent initialized successfully")
    print("Agent is ready to find optimal paths in the knowledge graph")


if __name__ == "__main__":
    main()
