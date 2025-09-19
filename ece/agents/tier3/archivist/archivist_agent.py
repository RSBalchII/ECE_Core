# ece/agents/tier3/archivist/archivist_agent.py
#!/usr/bin/env python3
"""
Archivist Agent for the External Context Engine (ECE).

The Archivist is the master controller of the Tier 3 Memory Cortex. It serves as the
primary API gateway for external requests for context and acts as the central coordinator
for all long-term memory operations. This version also includes continuous temporal scanning
functionality to maintain a chronological record of all processed information.
"""

import uvicorn
import httpx
import asyncio
import redis
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import os
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ECE Archivist Agent",
    description="The Archivist is the master controller of the Tier 3 Memory Cortex.",
    version="1.0.0"
)

class ContextRequest(BaseModel):
    """Model for context request from external modules."""
    query: str
    user_id: Optional[str] = None

class ContextResponse(BaseModel):
    """Model for context response to external modules."""
    context: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class DistillerData(BaseModel):
    """Model for data received from the Distiller agent."""
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    summary: str

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

class TemporalNodeRequest(BaseModel):
    """Model for temporal node requests."""
    timestamp: str

class MemoryLinkRequest(BaseModel):
    """Model for linking memory to temporal nodes."""
    memory_node_id: int
    timestamp: str

from ece.agents.clients import DistillerClient, QLearningAgentClient, InjectorClient

# Initialize clients
distiller_client = DistillerClient(base_url="http://distiller:8001")
qlearning_client = QLearningAgentClient()
injector_client = InjectorClient()

# Redis client for cache monitoring
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    password=os.environ.get('REDIS_PASSWORD'),
    db=0,
    decode_responses=True
)

# Track processed entries
processed_entries_key = "archivist:processed_entries"

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE Archivist Agent is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/context", response_model=ContextResponse)
async def get_context(request: ContextRequest):
    """
    External API endpoint to handle context requests.

    Args:
        request: ContextRequest containing the query

    Returns:
        ContextResponse with relevant context
    """
    try:
        logger.info(f"Received context request: {request.query}")

        # TODO: In a real implementation, parse the query to identify start/end nodes for QLearningAgent.
        # This would likely involve an NLP agent or a dedicated query parsing module.
        start_node = "concept_start"  # Placeholder
        end_node = "concept_end"    # Placeholder

        # Call QLearningAgent to find optimal paths
        paths = await qlearning_client.find_optimal_path(start_node, end_node)

        # Synthesize context from paths with more sophisticated processing
        context = []
        for i, path in enumerate(paths):
            # Extract key information from the path
            path_info = {
                "path_id": i,
                "nodes": path.nodes,
                "relationships": path.relationships,
                "relevance_score": path.score,
                "path_length": path.length
            }

            # Add additional context information
            if path.nodes:
                path_info["start_node"] = path.nodes[0] if len(path.nodes) > 0 else None
                path_info["end_node"] = path.nodes[-1] if len(path.nodes) > 0 else None

            # Process relationships to extract key information
            if path.relationships:
                path_info["relationship_types"] = list(set(rel.get("type", "UNKNOWN") for rel in path.relationships))
                path_info["entities_involved"] = list(set(
                    [rel.get("start_id") for rel in path.relationships if rel.get("start_id")] +
                    [rel.get("end_id") for rel in path.relationships if rel.get("end_id")]
                ))

            context.append(path_info)

        # Sort paths by relevance score (descending)
        context.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # Limit the number of paths returned to prevent overwhelming the client
        max_paths = 10
        context = context[:max_paths]

        return ContextResponse(
            context=context,
            metadata={
                "query": request.query,
                "timestamp": datetime.now().isoformat(),
                "source": "archivist",
                "paths_found": len(paths),
                "paths_returned": len(context)
            }
        )
    except Exception as e:
        logger.error(f"Error processing context request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/internal/data_to_archive")
async def receive_distiller_data(data: DistillerData):
    """
    Internal endpoint to receive structured data from the Distiller.

    Args:
        data: DistillerData containing entities, relationships, and summary

    Returns:
        Status of data processing
    """
    try:
        logger.info(f"Received data from Distiller: {len(data.entities)} entities, {len(data.relationships)} relationships")

        # Log the received data for debugging
        logger.debug(f"Distiller data: {data}")
        logger.debug(f"Distiller data type: {type(data)}")

        # Apply business logic to filter and process the data
        # For demonstration, we'll implement some basic filtering rules:

        # 1. Filter entities - only send entities with certain types or properties
        filtered_entities = []
        for entity in data.entities:
            # Example business rule: Only send entities with a 'name' property
            if entity.get('properties', {}).get('name'):
                # Example business rule: Only send entities of certain types
                entity_type = entity.get('type', '')
                if entity_type in ['Concept', 'Person', 'Organization', 'Event', 'Product']:
                    filtered_entities.append(entity)

        # 2. Filter relationships - only send relationships with certain types or properties
        filtered_relationships = []
        for relationship in data.relationships:
            # Example business rule: Only send relationships with a 'type' property
            if relationship.get('type'):
                # Example business rule: Only send relationships of certain types
                rel_type = relationship.get('type', '')
                if rel_type in ['RELATED_TO', 'PART_OF', 'CREATED_BY', 'WORKS_FOR', 'LOCATED_IN']:
                    filtered_relationships.append(relationship)

        # 3. Apply additional business rules
        # Example: Only send data if there are at least 1 entity and 1 relationship
        if len(filtered_entities) < 1 or len(filtered_relationships) < 1:
            logger.info("Data does not meet minimum criteria for archiving")
            return {"status": "filtered", "message": "Data filtered out by business rules"}

        # Example: Limit the number of entities and relationships to prevent overwhelming the database
        max_entities = 50
        max_relationships = 100
        if len(filtered_entities) > max_entities:
            logger.warning(f"Truncating entities from {len(filtered_entities)} to {max_entities}")
            filtered_entities = filtered_entities[:max_entities]
        if len(filtered_relationships) > max_relationships:
            logger.warning(f"Truncating relationships from {len(filtered_relationships)} to {max_relationships}")
            filtered_relationships = filtered_relationships[:max_relationships]

        # Log the filtered data
        logger.info(f"Filtered data: {len(filtered_entities)} entities, {len(filtered_relationships)} relationships")
        logger.debug(f"Filtered entities: {filtered_entities}")
        logger.debug(f"Filtered relationships: {filtered_relationships}")

        # Convert filtered data to dict for sending to Injector
        data_dict = {
            "entities": filtered_entities,
            "relationships": filtered_relationships,
            "summary": data.summary
        }

        # Log before sending to Injector
        logger.info("Sending filtered data to Injector")
        logger.debug(f"Data to send: {data_dict}")

        # Check if injector_client is properly initialized
        if not hasattr(injector_client, 'send_data_for_injection'):
            logger.error("injector_client does not have send_data_for_injection method")
            raise HTTPException(status_code=500, detail="Injector client not properly initialized")

        # Check if send_data_for_injection is callable
        if not callable(getattr(injector_client, 'send_data_for_injection', None)):
            logger.error("injector_client.send_data_for_injection is not callable")
            raise HTTPException(status_code=500, detail="Injector client method not callable")

        # Send data to Injector for writing to Neo4j
        try:
            result = await injector_client.send_data_for_injection(data_dict)
            logger.debug(f"Result from injector_client.send_data_for_injection: {result}")
            logger.debug(f"Result type: {type(result)}")
        except Exception as e:
            logger.error(f"Error calling injector_client.send_data_for_injection: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"Error calling injector: {type(e).__name__}: {e}")

        # Log the result from Injector
        logger.info(f"Received response from Injector: {result}")
        logger.debug(f"Result type: {type(result)}")

        if result.get("success"):
            logger.info("Data successfully sent to Injector")
            return {"status": "processed", "message": "Data sent to Injector successfully"}
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.debug(f"error_msg: {error_msg}, type: {type(error_msg)}")
            # Check if error_msg is callable (it shouldn't be)
            if callable(error_msg):
                logger.error("error_msg is callable, which is unexpected")
                raise HTTPException(status_code=500, detail="error_msg is callable")
            logger.error(f"Failed to send data to Injector: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Failed to inject data: {error_msg}")
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error processing distiller data: {str(e)}", exc_info=True)
        error_str = str(e)
        logger.debug(f"error_str: {error_str}, type: {type(error_str)}")
        # Check if error_str is callable (it shouldn't be)
        if callable(error_str):
            logger.error("error_str is callable, which is unexpected")
            raise HTTPException(status_code=500, detail="error_str is callable")
        # Check if there's any place in error_str where we might be calling a string
        if "'str' object is not callable" in error_str:
            logger.error("Detected 'str' object is not callable error in error_str")
            # Extract the original error from the error_str
            # This is a hacky way to get the original error, but it should work for debugging
            import re
            match = re.search(r"'([^']+)' object is not callable", error_str)
            if match:
                obj_str = match.group(1)
                logger.error(f"Object that is not callable: {obj_str}")
                # Try to identify where this object is coming from
                if obj_str in ["error", "result", "data", "response"]:
                    logger.error(f"Object {obj_str} might be accidentally called as a function")
        raise HTTPException(status_code=500, detail=f"Internal server error: {error_str}")

@app.post("/internal/handle_truncated_entries")
async def handle_truncated_entries(keys: List[str]):
    """
    Internal endpoint to handle truncated entries from the Context Cache.

    Args:
        keys: A list of keys for the truncated entries.
    """
    try:
        logger.info(f"Received {len(keys)} truncated entries to process.")
        
        for key in keys:
            # Retrieve the entry from the cache before it's deleted
            entry = redis_client.hgetall(key)
            if entry:
                value = entry.get("value", "")
                if value:
                    # Process the entry
                    success = await _process_cache_entry(key, value)
                    if not success:
                        logger.warning(f"Failed to process truncated cache entry: {key}")
        
        return {"status": "processed"}
    except Exception as e:
        logger.error(f"Error handling truncated entries: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

async def _process_cache_entry(key: str, value: str) -> bool:
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
        # Note: Using datetime.now() for timestamp. If the cache entry itself contains a timestamp,
        # it would be more accurate to use that. Assuming 'value' does not contain it for now.
        distiller_result = await distiller_client.process_text(value, "context_cache")

        if "error" in distiller_result:
            logger.error(f"Distiller processing failed for {key}: {distiller_result['error']}")
            return False

        logger.info(f"Distiller processing successful for {key}")
        logger.debug(f"Distiller result: {distiller_result}")

        # Step 2: Send to Injector for database storage
        injector_result = await injector_client.send_data_for_injection(distiller_result)

        if injector_result.get("status") != "processed":
            logger.error(f"Injector processing failed for {key}: {injector_result.get('message', 'Unknown error')}")
            return False

        logger.info(f"Injector processing successful for {key}")
        logger.debug(f"Injector result: {injector_result}")

        # Step 3: Refine relationships in the Q-Learning Agent
        path = MemoryPath(nodes=[entity['id'] for entity in distiller_result.get('entities', [])])
        await qlearning_client.refine_relationships(path, reward=1.0) # Positive reward for successful processing

        # Step 4: Link to temporal spine if we have a memory node ID
        memory_node_id = injector_result.get("memory_node_id")
        timestamp = distiller_result.get("timestamp", datetime.now().isoformat())

        if memory_node_id:
            # Get or create the time node
            timenode_result = await injector_client.get_or_create_timenode(timestamp)

            if "error" not in timenode_result:
                # Link the memory to the time node
                link_success = await injector_client.link_memory_to_timenode(memory_node_id, timestamp)

                if link_success:
                    logger.info(f"Successfully linked memory {memory_node_id} to temporal spine")
                else:
                    logger.warning(f"Failed to link memory {memory_node_id} to temporal spine")
            else:
                logger.warning(f"Failed to create time node: {timenode_result['error']}")

        # Mark as processed
        redis_client.sadd(processed_entries_key, key)

        return True
    except httpx.ConnectError as e:
        logger.error(f"Connection error processing cache entry {key}: {str(e)}")
        # Try to reconnect
        if not await _reconnect_redis():
            return False
        # Retry processing
        return await _process_cache_entry(key, value)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error processing cache entry {key}: {str(e)}")
        # Try to reconnect
        if not await _reconnect_redis():
            return False
        # Retry processing
        return await _process_cache_entry(key, value)
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error processing cache entry {key}: {str(e)}")
        # Try to reconnect
        if not await _reconnect_redis():
            return False
        # Retry processing
        return await _process_cache_entry(key, value)
    except redis.TimeoutError as e:
        logger.error(f"Redis timeout error processing cache entry {key}: {str(e)}")
        # Try to reconnect
        if not await _reconnect_redis():
            return False
        # Retry processing
        return await _process_cache_entry(key, value)
    except Exception as e:
        logger.error(f"Error processing cache entry {key}: {str(e)}", exc_info=True)
        return False

async def _scan_cache():
    """Scan the Redis cache for new entries to process."""
    try:
        # Get all keys with the context_cache prefix
        keys = redis_client.keys("context_cache:*")

        if not keys:
            logger.debug("No cache entries found to process")
            return

        logger.info(f"Found {len(keys)} cache entries to process")

        # Get already processed entries
        processed_entries = redis_client.smembers(processed_entries_key)

        # Process each unprocessed entry
        for key in keys:
            try:
                # Extract the actual key name (remove prefix)
                actual_key = key.replace("context_cache:", "")

                # Skip if already processed
                if actual_key in processed_entries:
                    continue

                # Get the value
                entry_data = redis_client.hgetall(key)
                if not entry_data:
                    continue

                value = entry_data.get("value", "")
                if not value:
                    continue

                # Process the entry
                success = await _process_cache_entry(actual_key, value)

                if not success:
                    logger.warning(f"Failed to process cache entry: {actual_key}")
            except redis.ConnectionError as e:
                logger.error(f"Redis connection error while processing key {key}: {str(e)}")
                # Try to reconnect
                if not await _reconnect_redis():
                    raise
                # Retry processing this key
                continue
            except redis.TimeoutError as e:
                logger.error(f"Redis timeout error while processing key {key}: {str(e)}")
                # Try to reconnect
                if not await _reconnect_redis():
                    raise
                # Retry processing this key
                continue
            except Exception as e:
                logger.error(f"Error processing cache entry {key}: {str(e)}", exc_info=True)
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error while scanning cache: {str(e)}")
        # Try to reconnect
        if not await _reconnect_redis():
            raise
    except redis.TimeoutError as e:
        logger.error(f"Redis timeout error while scanning cache: {str(e)}")
        # Try to reconnect
        if not await _reconnect_redis():
            raise
    except Exception as e:
        logger.error(f"Error scanning cache: {str(e)}", exc_info=True)

async def continuous_temporal_scanning():
    """Run the continuous temporal scanning process."""
    logger.info("Starting continuous temporal scanning")

    # Connect to Redis with retry logic
    max_retries = 5
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            redis_client.ping()
            logger.info("Connected to Redis for temporal scanning")
            break
        except Exception as e:
            logger.warning(f"Failed to connect to Redis (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Failed to connect to Redis after all retries")
                return

    # Main scanning loop
    while True:
        try:
            # Scan the cache for new entries
            await _scan_cache()

            # Wait before next scan
            await asyncio.sleep(5)  # Scan every 5 seconds
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error in temporal scanning loop: {str(e)}")
            # Try to reconnect
            await _reconnect_redis()
        except redis.TimeoutError as e:
            logger.error(f"Redis timeout error in temporal scanning loop: {str(e)}")
            # Try to reconnect
            await _reconnect_redis()
        except Exception as e:
            logger.error(f"Error in temporal scanning loop: {str(e)}", exc_info=True)
            # Wait a bit before retrying
            await asyncio.sleep(10)

async def _reconnect_redis():
    """Reconnect to Redis with exponential backoff."""
    max_retries = 5
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            redis_client.ping()
            logger.info("Reconnected to Redis")
            return True
        except Exception as e:
            logger.warning(f"Failed to reconnect to Redis (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Failed to reconnect to Redis after all retries")
                return False

# Start the continuous temporal scanning when the app starts
@app.on_event("startup")
async def startup_event():
    """Start the continuous temporal scanning process on startup."""
    # Start the temporal scanning in the background
    asyncio.create_task(continuous_temporal_scanning())

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    await distiller_client.client.aclose()
    await qlearning_client.client.aclose()
    await injector_client.client.aclose()

if __name__ == "__main__":
    uvicorn.run(
        "archivist_agent:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )
