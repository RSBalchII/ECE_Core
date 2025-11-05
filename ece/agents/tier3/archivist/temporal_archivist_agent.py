#!/usr/bin/env python3
"""
Temporal Archivist Agent for the External Context Engine (ECE).

The Temporal Archivist is a persistent, background process that continuously monitors
the Redis cache for new data. When new data is detected, it coordinates with the
Distiller and Injector agents to process and store the information in the Neo4j
knowledge graph, while maintaining a chronological record of all processed information.
"""

import asyncio
import httpx
import logging
from datetime import datetime
import redis
import json
from typing import Dict, Any, List, Optional
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DistillerClient:
    """Client for communicating with the Distiller agent."""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def process_text(
        self, text: str, source: str = "context_cache"
    ) -> Dict[str, Any]:
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
                "timestamp": datetime.now().isoformat(),
            }

            response = await self.client.post(
                f"{self.base_url}/process_text", json=data, timeout=30.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Distiller returned status {response.status_code}")
                return {"error": f"Distiller returned status {response.status_code}"}
        except Exception as e:
            logger.error(f"Error calling Distiller: {str(e)}")
            return {"error": f"Error calling Distiller: {str(e)}"}


class InjectorClient:
    """Client for communicating with the Injector agent."""

    def __init__(self, base_url: str = "http://localhost:8004"):
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
            logger.info(
                f"Sending data to Injector at {self.base_url}/internal/data_to_inject"
            )
            logger.debug(f"Data being sent: {data}")

            response = await self.client.post(
                f"{self.base_url}/internal/data_to_inject", json=data, timeout=30.0
            )

            logger.info(
                f"Received response from Injector: status_code={response.status_code}"
            )
            logger.debug(f"Response headers: {response.headers}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successful response from Injector: {result}")
                logger.debug(f"Result type: {type(result)}")
                return result
            else:
                error_text = response.text
                logger.error(
                    f"Injector returned status {response.status_code} with body: {error_text}"
                )
                logger.debug(f"Error text type: {type(error_text)}")
                return {
                    "success": False,
                    "error": f"Injector returned status {response.status_code}: {error_text}",
                }
        except httpx.ConnectError as e:
            logger.error(f"Connection error calling Injector: {str(e)}")
            return {"success": False, "error": f"Connection error: {str(e)}"}
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error calling Injector: {str(e)}")
            return {"success": False, "error": f"Timeout error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error calling Injector: {str(e)}", exc_info=True)
            error_str = str(e)
            logger.debug(f"Error string: {error_str}, type: {type(error_str)}")
            return {"success": False, "error": f"Unexpected error: {error_str}"}


class Neo4jTemporalManager:
    """Manager for Neo4j temporal operations."""

    def __init__(self, base_url: str = "http://localhost:8004"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

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
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            data = {"timestamp": dt.isoformat()}

            response = await self.client.post(
                f"{self.base_url}/internal/temporal/get_or_create_timenode",
                json=data,
                timeout=30.0,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Temporal service returned status {response.status_code}")
                return {
                    "error": f"Temporal service returned status {response.status_code}"
                }
        except Exception as e:
            logger.error(f"Error calling temporal service: {str(e)}")
            return {"error": f"Error calling temporal service: {str(e)}"}

    async def link_memory_to_timenode(
        self, memory_node_id: int, timestamp: str
    ) -> bool:
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
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            data = {"memory_node_id": memory_node_id, "timestamp": dt.isoformat()}

            response = await self.client.post(
                f"{self.base_url}/internal/temporal/link_memory_to_timenode",
                json=data,
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("success", False)
            else:
                logger.error(f"Temporal service returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error calling temporal service: {str(e)}")
            return False


class TemporalArchivistAgent:
    """Temporal Archivist Agent that runs as a continuous background process."""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        redis_db: int = 0,
    ):
        """
        Initialize the Temporal Archivist Agent.

        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_password: Redis password
            redis_db: Redis database number
        """
        # Initialize Redis connection
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            decode_responses=True,
        )

        # Initialize clients
        self.distiller_client = DistillerClient()
        self.injector_client = InjectorClient()
        self.temporal_manager = Neo4jTemporalManager()

        # Track processed entries
        self.processed_entries_key = "archivist:processed_entries"

        # Health check
        self.healthy = True

        logger.info("Temporal Archivist Agent initialized")

    def _connect_redis(self):
        """Establish connection to Redis with retry logic."""
        max_retries = 5
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                self.redis_client.ping()
                logger.info("Connected to Redis")
                return True
            except Exception as e:
                logger.warning(
                    f"Failed to connect to Redis (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("Failed to connect to Redis after all retries")
                    return False

    async def _process_cache_entry(self, key: str, value: str) -> bool:
        """
        Process a single cache entry.

        Args:
            key: The cache key
            value: The cache value

        Returns:
            True if processing was successful, False otherwise
        """
        try:
            logger.info(f"Processing cache entry: {key}")

            # Step 1: Send to Distiller for processing
            distiller_result = await self.distiller_client.process_text(
                value, "context_cache"
            )

            if "error" in distiller_result:
                logger.error(
                    f"Distiller processing failed for {key}: {distiller_result['error']}"
                )
                return False

            logger.info(f"Distiller processing successful for {key}")
            logger.debug(f"Distiller result: {distiller_result}")

            # Step 2: Send to Injector for database storage
            injector_result = await self.injector_client.send_data_for_injection(
                distiller_result
            )

            if not injector_result.get("success", False):
                logger.error(
                    f"Injector processing failed for {key}: {injector_result.get('error', 'Unknown error')}"
                )
                return False

            logger.info(f"Injector processing successful for {key}")
            logger.debug(f"Injector result: {injector_result}")

            # Step 3: Link to temporal spine if we have a memory node ID
            memory_node_id = injector_result.get("memory_node_id")
            timestamp = distiller_result.get("timestamp", datetime.now().isoformat())

            if memory_node_id:
                # Get or create the time node
                timenode_result = await self.temporal_manager.get_or_create_timenode(
                    timestamp
                )

                if "error" not in timenode_result:
                    # Link the memory to the time node
                    link_success = await self.temporal_manager.link_memory_to_timenode(
                        memory_node_id, timestamp
                    )

                    if link_success:
                        logger.info(
                            f"Successfully linked memory {memory_node_id} to temporal spine"
                        )
                    else:
                        logger.warning(
                            f"Failed to link memory {memory_node_id} to temporal spine"
                        )
                else:
                    logger.warning(
                        f"Failed to create time node: {timenode_result['error']}"
                    )

            # Mark as processed
            self.redis_client.sadd(self.processed_entries_key, key)

            return True
        except Exception as e:
            logger.error(f"Error processing cache entry {key}: {str(e)}", exc_info=True)
            return False

    async def _scan_cache(self):
        """Scan the Redis cache for new entries to process."""
        try:
            # Get all keys with the context_cache prefix
            keys = self.redis_client.keys("context_cache:*")

            if not keys:
                logger.debug("No cache entries found to process")
                return

            logger.info(f"Found {len(keys)} cache entries to process")

            # Get already processed entries
            processed_entries = self.redis_client.smembers(self.processed_entries_key)

            # Process each unprocessed entry
            for key in keys:
                # Extract the actual key name (remove prefix)
                actual_key = key.replace("context_cache:", "")

                # Skip if already processed
                if actual_key in processed_entries:
                    continue

                # Get the value
                entry_data = self.redis_client.hgetall(key)
                if not entry_data:
                    continue

                value = entry_data.get("value", "")
                if not value:
                    continue

                # Process the entry
                success = await self._process_cache_entry(actual_key, value)

                if not success:
                    logger.warning(f"Failed to process cache entry: {actual_key}")
        except Exception as e:
            logger.error(f"Error scanning cache: {str(e)}", exc_info=True)

    async def run(self):
        """Run the Temporal Archivist Agent as a continuous background process."""
        logger.info("Starting Temporal Archivist Agent")

        # Connect to Redis
        if not self._connect_redis():
            logger.error("Failed to connect to Redis. Exiting.")
            return

        # Main processing loop
        while self.healthy:
            try:
                # Scan the cache for new entries
                await self._scan_cache()

                # Wait before next scan
                await asyncio.sleep(5)  # Scan every 5 seconds
            except KeyboardInterrupt:
                logger.info("Received interrupt signal. Shutting down.")
                self.healthy = False
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                # Wait a bit before retrying
                await asyncio.sleep(10)

        logger.info("Temporal Archivist Agent stopped")

    def stop(self):
        """Stop the Temporal Archivist Agent."""
        logger.info("Stopping Temporal Archivist Agent")
        self.healthy = False


# Main execution
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Temporal Archivist Agent")
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port")
    parser.add_argument("--redis-password", help="Redis password")
    parser.add_argument("--redis-db", type=int, default=0, help="Redis database")

    args = parser.parse_args()

    # Create and run the agent
    agent = TemporalArchivistAgent(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        redis_password=args.redis_password,
        redis_db=args.redis_db,
    )

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        agent.stop()
        logger.info("Agent stopped by user")
