# ece/agents/clients.py
import json
import uuid
import httpx
import os
from typing import Dict, Any, List
from pydantic import BaseModel
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def sanitize_entities_for_injection(data: dict) -> dict:
    if "entities" in data and isinstance(data["entities"], list):
        for entity in data["entities"]:
            if not entity.get("id"):
                entity["id"] = str(uuid.uuid4())
    return data

class DistillerClient:
    """Client for communicating with the Distiller agent."""

    def __init__(self, base_url: str = os.getenv("DISTILLER_URL", "http://distiller:8001")):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def process_text(self, text: str, source: str = "context_cache") -> Dict[str, Any]:
        """
        Send text to the Distiller agent for processing.

        Args:
            text: The text to process
            source: The source of the text

        Returns:
            Structured data from the Distiller
        """
        try:
            data = {
                "text": text,
                "source": source,
                "timestamp": datetime.now().isoformat()
            }

            response = await self.client.post(
                f"{self.base_url}/process_text",
                json=data,
                timeout=30.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Distiller returned status {response.status_code}")
                return {"error": f"Distiller returned status {response.status_code}"}
        except Exception as e:
            logger.error(f"Error calling Distiller: {str(e)}")
            return {"error": f"Error calling Distiller: {str(e)}"}

class QLearningPathRequest(BaseModel):
    """Model for requesting paths from the QLearningAgent."""
    start_node: str
    end_node: str

class MemoryPath(BaseModel):
    """Model for a path through the knowledge graph."""
    nodes: List[str] = []
    relationships: List[Dict[str, Any]] = []
    score: float = 0.0
    length: int = 0

class QLearningAgentClient:
    """Client for communicating with the QLearningAgent."""

    def __init__(self, base_url: str = os.getenv("QLEARNING_URL", "http://qlearning:8002")):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def find_optimal_path(self, start_node: str, end_node: str) -> List[MemoryPath]:
        """
        Find the optimal path between start and end nodes using Q-learning.

        Args:
            start_node: The starting node ID
            end_node: The target node ID

        Returns:
            List of MemoryPath objects ranked by Q-values
        """
        try:
            request_data = QLearningPathRequest(
                start_node=start_node,
                end_node=end_node
            )

            response = await self.client.post(
                f"{self.base_url}/find_optimal_path",
                json=request_data.dict()
            )

            if response.status_code == 200:
                paths_data = response.json()
                paths = [MemoryPath(**path_data) for path_data in paths_data]
                return paths
            else:
                logger.error(f"QLearningAgent returned status {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error calling QLearningAgent: {str(e)}")
            return []

    async def refine_relationships(self, path: MemoryPath, reward: float) -> Dict[str, Any]:
        """
        Send a path and a reward to the QLearningAgent to refine relationships.

        Args:
            path: The path to refine.
            reward: The reward for the path.

        Returns:
            The response from the QLearningAgent.
        """
        try:
            request_data = {
                "path": path.dict(),
                "reward": reward
            }

            response = await self.client.post(
                f"{self.base_url}/refine_relationships",
                json=request_data
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"QLearningAgent returned status {response.status_code}")
                return {"error": f"QLearningAgent returned status {response.status_code}"}
        except Exception as e:
            logger.error(f"Error calling QLearningAgent: {str(e)}")
            return {"error": f"Error calling QLearningAgent: {str(e)}"}

class InjectorClient:
    """Client for communicating with the Injector agent."""

    def __init__(self, base_url: str = os.getenv("INJECTOR_URL", "http://injector:8004")):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def send_data_for_injection(self, data: dict) -> dict:
        """
        Send data to the Injector agent for writing to the Neo4j database.

        Args:
            data (dict): Structured data to be injected into the Neo4j database.

        Returns:
            dict: Result of the injection operation.
        """
        try:
            logger.info(f"Sending data to Injector at {self.base_url}/internal/data_to_inject")
            logger.debug(f"Data being sent: {data}")

            # Convert datetime objects to ISO strings in the data
            from datetime import datetime
            def convert_datetime(obj):
                if isinstance(obj, dict):
                    return {k: convert_datetime(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_datetime(item) for item in obj]
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                else:
                    return obj
            
            sanitized_data = convert_datetime(data)
            logger.debug(f"Sanitized data: {sanitized_data}")

            # Create a POML request
            from ece.common.poml_schemas import POML
            poml_request = POML(
                identity={
                    "name": "ArchivistAgent",
                    "version": "1.0",
                    "type": "Memory Cortex Controller"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Send data to Injector for persistence in Neo4j knowledge graph."
                },
                directive={
                    "goal": "Request data injection into Neo4j knowledge graph.",
                    "task": {
                        "name": "InjectData",
                        "data": sanitized_data
                    }
                }
            )
            
            # Convert POML to dict and ensure all datetime objects are properly serialized
            poml_dict = poml_request.dict()
            logger.debug(f"POML dict before final sanitization: {poml_dict}")

            # Final sanitization pass to ensure no datetime objects remain
            final_sanitized_data = convert_datetime(poml_dict)
            logger.debug(f"Final sanitized POML dict: {final_sanitized_data}")

            response = await self.client.post(
                f"{self.base_url}/internal/data_to_inject",
                json=final_sanitized_data,  # Use the fully sanitized data
                timeout=30.0  # Add a timeout
            )

            logger.info(f"Received response from Injector: status_code={response.status_code}")
            logger.debug(f"Response headers: {response.headers}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successful response from Injector: {result}")
                logger.debug(f"Result type: {type(result)}")
                
                # Extract the actual result from the POML response
                if "node_data" in result:
                    return result["node_data"]
                else:
                    return result
            else:
                error_text = response.text
                logger.error(f"Injector returned status {response.status_code} with body: {error_text}")
                logger.debug(f"Error text type: {type(error_text)}")
                return {
                    "success": False,
                    "error": f"Injector returned status {response.status_code}: {error_text}"
                }
        except httpx.ConnectError as e:
            logger.error(f"Connection error calling Injector: {str(e)}")
            return {
                "success": False,
                "error": f"Connection error: {str(e)}"
            }
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error calling Injector: {str(e)}")
            return {
                "success": False,
                "error": f"Timeout error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error calling Injector: {str(e)}", exc_info=True)
            error_str = str(e)
            logger.debug(f"Error string: {error_str}, type: {type(error_str)}")
            # Check if error_str is callable (it shouldn't be)
            if callable(error_str):
                logger.error("error_str is callable, which is unexpected")
                return {
                    "success": False,
                    "error": "Unexpected callable error string"
                }
            return {
                "success": False,
                "error": f"Unexpected error: {error_str}"
            }

    async def get_or_create_timenode(self, timestamp: str) -> Dict[str, Any]:
        """
        Create a chronological tree of nodes: (Year)->[:HAS_MONTH]->(Month)->[:HAS_DAY]->(Day).

        Args:
            timestamp: The timestamp to create the chronological tree for (ISO format)

        Returns:
            Dictionary containing the day node information
        """
        try:
            # Parse the timestamp
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            # Create a POML request
            from ece.common.poml_schemas import POML
            poml_request = POML(
                identity={
                    "name": "ArchivistAgent",
                    "version": "1.0",
                    "type": "Memory Cortex Controller"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Request creation of temporal node in Neo4j knowledge graph."
                },
                directive={
                    "goal": "Request creation of temporal node.",
                    "task": {
                        "name": "CreateTimeNode",
                        "timestamp": dt.isoformat()
                    }
                }
            )

            response = await self.client.post(
                f"{self.base_url}/internal/temporal/get_or_create_timenode",
                json=poml_request.dict(),
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                # Extract the actual result from the POML response
                if "node_data" in result:
                    return result["node_data"]
                else:
                    return result
            else:
                logger.error(f"Temporal service returned status {response.status_code}")
                return {"error": f"Temporal service returned status {response.status_code}"}
        except Exception as e:
            logger.error(f"Error calling temporal service: {str(e)}")
            return {"error": f"Error calling temporal service: {str(e)}"}

    async def link_memory_to_timenode(self, memory_node_id: int, timestamp: str) -> bool:
        """
        Create a [:OCCURRED_AT] relationship to the appropriate Day node.

        Args:
            memory_node_id: The ID of the memory node to link
            timestamp: The timestamp to link the memory to (ISO format)

        Returns:
            True if the relationship was created successfully, False otherwise
        """
        try:
            # Parse the timestamp
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            # Create a POML request
            from ece.common.poml_schemas import POML
            poml_request = POML(
                identity={
                    "name": "ArchivistAgent",
                    "version": "1.0",
                    "type": "Memory Cortex Controller"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Request linking of memory node to temporal node in Neo4j knowledge graph."
                },
                directive={
                    "goal": "Request linking of memory node to temporal node.",
                    "task": {
                        "name": "LinkMemoryToTimeNode",
                        "memory_node_id": memory_node_id,
                        "timestamp": dt.isoformat()
                    }
                }
            )

            response = await self.client.post(
                f"{self.base_url}/internal/temporal/link_memory_to_timenode",
                json=poml_request.dict(),
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                # Extract the actual result from the POML response
                if "node_data" in result:
                    return result["node_data"].get("success", False)
                else:
                    return result.get("success", False)
            else:
                logger.error(f"Temporal service returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error calling temporal service: {str(e)}")
            return False

class ArchivistClient:
    """Client for communicating with the Archivist agent."""

    def __init__(self, base_url: str = os.getenv("ARCHIVIST_URL", "http://archivist:8003")):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def handle_truncated_entries(self, keys: List[str]) -> Dict[str, Any]:
        """
        Send truncated entry keys to the Archivist agent.

        Args:
            keys: A list of keys for the truncated entries.

        Returns:
            The response from the Archivist agent.
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/internal/handle_truncated_entries",
                json=keys,
                timeout=30.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Archivist returned status {response.status_code}")
                return {"error": f"Archivist returned status {response.status_code}"}
        except Exception as e:
            logger.error(f"Error calling Archivist: {str(e)}")
            return {"error": f"Error calling Archivist: {str(e)}"}