from typing import Dict, Any, List
import logging
from datetime import datetime
from ece.agents.tier3.injector.db_manager import Neo4jManager # Import the Neo4jManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InjectorAgent:
    """
    The InjectorAgent is responsible for orchestrating data injection into the Neo4j knowledge graph.
    It utilizes the Neo4jManager to perform database operations.
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """
        Initializes the InjectorAgent with Neo4j connection details.

        Args:
            neo4j_uri: URI for the Neo4j database.
            neo4j_user: Username for Neo4j authentication.
            neo4j_password: Password for Neo4j authentication.
        """
        self.neo4j_manager = Neo4jManager(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)
        self.neo4j_manager.connect() # Establish connection on initialization
        logger.info("InjectorAgent initialized and connected to Neo4j.")

    def receive_data_for_injection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives structured data and injects it into the Neo4j knowledge graph.

        Args:
            data: A dictionary containing 'entities' and 'relationships' to be injected.

        Returns:
            A dictionary indicating the success or failure of the injection.
        """
        logger.info(f"InjectorAgent received data for injection. Entities: {len(data.get('entities', []))}, Relationships: {len(data.get('relationships', []))}")
        try:
            # Translate the incoming data into Cypher queries
            cypher_queries = self.neo4j_manager._translate_to_cypher(data) # Use the internal method for now

            if not cypher_queries:
                logger.warning("No Cypher queries generated from the received data.")
                return {"success": True, "message": "No data to inject."}

            # Execute the queries within a transaction
            if self.neo4j_manager.execute_transaction(cypher_queries):
                logger.info("Data injected successfully into Neo4j.")
                return {"success": True, "message": "Data injected successfully."}
            else:
                logger.error("Failed to inject data into Neo4j.")
                return {"success": False, "message": "Failed to inject data."}
        except Exception as e:
            logger.error(f"Error during data injection: {e}")
            return {"success": False, "message": f"Error during data injection: {str(e)}"}

    def get_or_create_timenode(self, timestamp_str: str) -> Dict[str, Any]:
        """
        Gets or creates a time node in Neo4j for the given timestamp.

        Args:
            timestamp_str: The timestamp string (e.g., ISO format).

        Returns:
            A dictionary containing the time node information.
        """
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            result = self.neo4j_manager.get_or_create_timenode(timestamp)
            logger.info(f"Time node retrieved or created for {timestamp_str}: {result}")
            return {"success": True, "message": "Time node retrieved or created.", "time_node": result}
        except ValueError:
            logger.error(f"Invalid timestamp format: {timestamp_str}")
            return {"success": False, "message": "Invalid timestamp format. Please use ISO format."}
        except Exception as e:
            logger.error(f"Error getting or creating time node: {e}")
            return {"success": False, "message": f"Error getting or creating time node: {str(e)}"}

    def link_memory_to_timenode(self, memory_node_id: int, timestamp_str: str) -> Dict[str, Any]:
        """
        Links a memory node to a time node in Neo4j.

        Args:
            memory_node_id: The ID of the memory node.
            timestamp_str: The timestamp string (e.g., ISO format) of the time node to link to.

        Returns:
            A dictionary indicating the success or failure of the linking operation.
        """
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            if self.neo4j_manager.link_memory_to_timenode(memory_node_id, timestamp):
                logger.info(f"Memory node {memory_node_id} linked to time node for {timestamp_str}.")
                return {"success": True, "message": "Memory node linked to time node successfully."}
            else:
                logger.error(f"Failed to link memory node {memory_node_id} to time node for {timestamp_str}.")
                return {"success": False, "message": "Failed to link memory node to time node."}
        except ValueError:
            logger.error(f"Invalid timestamp format: {timestamp_str}")
            return {"success": False, "message": "Invalid timestamp format. Please use ISO format."}
        except Exception as e:
            logger.error(f"Error linking memory node to time node: {e}")
            return {"success": False, "message": f"Error linking memory node to time node: {str(e)}"}

    def __del__(self):
        """
        Ensures the Neo4j connection is closed when the InjectorAgent instance is destroyed.
        """
        if self.neo4j_manager:
            self.neo4j_manager.disconnect()
            logger.info("InjectorAgent disconnected from Neo4j.")
