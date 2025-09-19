"""
Neo4j Manager for QLearningAgent

This module provides the interface for connecting to and querying the Neo4j database
for the QLearningAgent's graph navigation functionality.
"""

import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Neo4jManager:
    """
    Manager for interacting with the Neo4j database for QLearningAgent operations.
    
    This class provides methods to:
    - Connect to the Neo4j database
    - Query graph structure (nodes and relationships)
    - Read and write Q-values as relationship properties
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize the Neo4jManager with connection parameters.
        
        Args:
            uri: The Neo4j database URI
            user: The Neo4j username
            password: The Neo4j password
        """
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None

    def connect(self) -> None:
        """Establish connection to the Neo4j database."""
        try:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            logger.info("Successfully connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j database: {e}")
            raise

    def close(self) -> None:
        """Close the connection to the Neo4j database."""
        if self._driver:
            self._driver.close()
            logger.info("Closed connection to Neo4j database")

    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a node by its ID from the Neo4j database.
        
        Args:
            node_id: The ID of the node to retrieve
            
        Returns:
            Dictionary representation of the node or None if not found
        """
        if not self._driver:
            raise Exception("Database not connected")
            
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n {id: $node_id}) RETURN n",
                node_id=node_id
            )
            record = result.single()
            if record:
                node = record["n"]
                return {
                    "id": node["id"],
                    "labels": list(node.labels),
                    "properties": dict(node)
                }
            return None

    def get_neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        """
        Get all neighboring nodes and relationships for a given node.
        
        Args:
            node_id: The ID of the node to get neighbors for
            
        Returns:
            List of dictionaries representing neighboring nodes and relationships
        """
        if not self._driver:
            raise Exception("Database not connected")
            
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (n {id: $node_id})-[r]->(m)
                RETURN n, r, m
                """,
                node_id=node_id
            )
            
            neighbors = []
            for record in result:
                relationship = record["r"]
                neighbor_node = record["m"]
                
                neighbors.append({
                    "from_node": node_id,
                    "to_node": neighbor_node["id"],
                    "relationship_type": relationship.type,
                    "relationship_properties": dict(relationship),
                    "neighbor_properties": dict(neighbor_node)
                })
                
            return neighbors

    def get_q_value(self, from_node_id: str, to_node_id: str, relationship_type: str) -> float:
        """
        Retrieve the Q-value for a specific relationship.
        
        Args:
            from_node_id: The ID of the starting node
            to_node_id: The ID of the ending node
            relationship_type: The type of relationship
            
        Returns:
            The Q-value for the relationship, or 0.0 if not found
        """
        if not self._driver:
            raise Exception("Database not connected")
            
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (n {id: $from_node_id})-[r:$rel_type]->(m {id: $to_node_id})
                RETURN r.q_value as q_value
                """,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                rel_type=relationship_type
            )
            record = result.single()
            if record and record["q_value"] is not None:
                return float(record["q_value"])
            return 0.0

    def update_q_value(self, from_node_id: str, to_node_id: str, relationship_type: str, q_value: float) -> None:
        """
        Update the Q-value for a specific relationship using MERGE to ensure relationship exists.
        
        Args:
            from_node_id: The ID of the starting node
            to_node_id: The ID of the ending node
            relationship_type: The type of relationship
            q_value: The new Q-value to set
        """
        if not self._driver:
            raise Exception("Database not connected")
            
        with self._driver.session() as session:
            # Use MERGE to ensure the relationship exists, then set the Q-value
            session.run(
                """
                MERGE (n {id: $from_node_id})
                MERGE (m {id: $to_node_id})
                MERGE (n)-[r:$rel_type]->(m)
                SET r.q_value = $q_value
                """,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                rel_type=relationship_type,
                q_value=q_value
            )
            logger.info(f"Updated Q-value for relationship {from_node_id}->{to_node_id}: {q_value}")

    def sync_q_values_to_graph(self, q_table: Dict[str, Dict[str, float]]) -> None:
        """
        Synchronize all Q-values from the in-memory Q-table to the Neo4j graph.
        
        Args:
            q_table: Dictionary mapping state-action pairs to Q-values
        """
        if not self._driver:
            raise Exception("Database not connected")
            
        with self._driver.session() as session:
            for state, actions in q_table.items():
                for action, q_value in actions.items():
                    # Parse state and action identifiers
                    # Format: state = "node_id", action = "to_node_id:relationship_type"
                    from_node_id = state
                    if ":" in action:
                        to_node_id, relationship_type = action.split(":", 1)
                        # Use MERGE to ensure the relationship exists, then set the Q-value
                        session.run(
                            """
                            MERGE (n {id: $from_node_id})
                            MERGE (m {id: $to_node_id})
                            MERGE (n)-[r:$rel_type]->(m)
                            SET r.q_value = $q_value
                            """,
                            from_node_id=from_node_id,
                            to_node_id=to_node_id,
                            rel_type=relationship_type,
                            q_value=q_value
                        )
            logger.info("Synchronized Q-values to Neo4j graph")

    def find_nodes_by_keywords(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Find nodes that have properties matching the given keywords.

        Args:
            keywords: A list of keywords to search for.

        Returns:
            A list of nodes that match the keywords.
        """
        if not self._driver:
            raise Exception("Database not connected")

        with self._driver.session() as session:
            query = """
            UNWIND $keywords as keyword
            MATCH (n)
            WHERE any(prop in keys(n) WHERE n[prop] CONTAINS keyword)
            RETURN n
            """
            result = session.run(query, keywords=keywords)
            
            nodes = []
            for record in result:
                node = record["n"]
                nodes.append({
                    "id": node["id"],
                    "labels": list(node.labels),
                    "properties": dict(node)
                })
            return nodes
