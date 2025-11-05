#!/usr/bin/env python3
"""
Enhanced Archivist Agent Implementation

This module enhances the Archivist agent to properly coordinate with the QLearning Agent
for context-aware responses and implements the required 1M token processing.
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

# Import UTCP data models for manual creation
from utcp.data.utcp_manual import UtcpManual
from utcp.data.tool import Tool
from utcp_http.http_call_template import HttpCallTemplate

# Import and set up ECE logging system
try:
    from ece.common.logging_config import get_logger

    logger = get_logger("archivist")
except ImportError:
    # Fallback if logging config not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Could not import ECE logging system, using default logging")

# Initialize FastAPI app
app = FastAPI(
    title="ECE Archivist Agent",
    description="The Archivist is the master controller of the Tier 3 Memory Cortex.",
    version="1.0.0",
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
distiller_client = DistillerClient(base_url="http://localhost:8001")
qlearning_client = QLearningAgentClient()
injector_client = InjectorClient()

# Redis client for cache monitoring
redis_client = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    password=os.environ.get("REDIS_PASSWORD"),
    db=0,
    decode_responses=True,
)


class EnhancedContextRequest(BaseModel):
    """Model for enhanced context requests."""

    query: str
    keywords: List[str] = []
    max_tokens: int = 1000000  # Allow up to 1M tokens as requested
    session_id: Optional[str] = None
    max_contexts: int = 10


class EnhancedContextResponse(BaseModel):
    """Model for enhanced context responses."""

    enhanced_context: str
    related_memories: List[Dict[str, Any]] = []
    session_id: str
    timestamp: str
    token_count: int = 0


# Track processed entries
processed_entries_key = "archivist:processed_entries"

# Key for tracking the last scan time for cache tailing
last_scan_time_key = "archivist:last_scan_time"


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE Archivist Agent is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


class MemoryContextRequest(BaseModel):
    """Model for memory context requests."""

    context_id: str
    max_contexts: int = 5  # Default to 5 contexts to prevent memory bloat


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
        end_node = "concept_end"  # Placeholder

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
                "path_length": path.length,
            }

            # Add additional context information
            if path.nodes:
                path_info["start_node"] = path.nodes[0] if len(path.nodes) > 0 else None
                path_info["end_node"] = path.nodes[-1] if len(path.nodes) > 0 else None

            # Process relationships to extract key information
            if path.relationships:
                path_info["relationship_types"] = list(
                    set([rel.get("type", "UNKNOWN") for rel in path.relationships])
                )
                path_info["entities_involved"] = list(
                    set(
                        [
                            rel.get("start_id")
                            for rel in path.relationships
                            if rel.get("start_id")
                        ]
                        + [
                            rel.get("end_id")
                            for rel in path.relationships
                            if rel.get("end_id")
                        ]
                    )
                )

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
                "paths_returned": len(context),
            },
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
        logger.info(
            f"Received data from Distiller: {len(data.entities)} entities, {len(data.relationships)} relationships"
        )

        # Log the received data for debugging
        logger.debug(f"Distiller data: {data}")
        logger.debug(f"Distiller data type: {type(data)}")

        # Apply business logic to filter and process the data
        # For demonstration, we'll implement some basic filtering rules:

        # Transform and filter entities - convert Distiller format to Injector format and add IDs
        filtered_entities = []
        for i, entity in enumerate(data.entities):
            # Transform entity from Distiller format to Injector format
            # Distiller format: {"text": "...", "label": "...", "description": "..."}
            # Injector format: {"id": "...", "type": "...", "properties": {...}}
            entity_text = entity.get("text", "")
            entity_label = entity.get("label", "Entity")

            # Generate a more robust ID that handles edge cases
            if entity_text:
                entity_id = f"entity_{i}_{abs(hash(entity_text))}"
            else:
                entity_id = f"entity_{i}_no_text"

            transformed_entity = {
                "id": entity_id,  # Generate ID based on index and text content
                "type": entity_label,  # Use label as type
                "properties": {
                    "name": entity_text,
                    "description": entity.get("description", ""),
                    "source_text": entity_text,
                },
            }

            # Apply business rules for filtering
            # Example business rule: Only send entities with a 'name' property
            if transformed_entity["properties"].get("name"):
                # Example business rule: Only send entities of certain types
                # Include common spaCy entity types and our custom types
                entity_type = transformed_entity.get("type", "")
                if entity_type in [
                    "Concept",
                    "Person",
                    "PERSON",
                    "Organization",
                    "ORG",
                    "Event",
                    "EVENT",
                    "Product",
                    "PRODUCT",
                    "GPE",
                    "DATE",
                    "TIME",
                    "ENTITY",
                ]:
                    filtered_entities.append(transformed_entity)

        # Transform and filter relationships - convert to expected format
        filtered_relationships = []
        for i, relationship in enumerate(data.relationships):
            # Transform relationship to expected format
            # For now, we'll create a simple relationship structure
            # In a real implementation, the Distiller would provide more detailed relationship info
            transformed_relationship = {
                "type": relationship.get("type", "RELATED_TO"),
                "start_id": f"relationship_start_{i}",
                "end_id": f"relationship_end_{i}",
                "start_type": relationship.get("start_type", "Entity"),
                "end_type": relationship.get("end_type", "Entity"),
                "properties": relationship.get("properties", {}),
            }

            # Apply business rules for filtering
            # Example business rule: Only send relationships with a 'type' property
            if transformed_relationship.get("type"):
                # Example business rule: Only send relationships of certain types
                rel_type = transformed_relationship.get("type", "")
                if rel_type in [
                    "RELATED_TO",
                    "PART_OF",
                    "CREATED_BY",
                    "WORKS_FOR",
                    "LOCATED_IN",
                ]:
                    filtered_relationships.append(transformed_relationship)

        # 3. Apply additional business rules
        # Example: Only send data if there are at least 1 entity OR 1 relationship
        if len(filtered_entities) < 1 and len(filtered_relationships) < 1:
            logger.info("Data does not meet minimum criteria for archiving")
            return {
                "status": "filtered",
                "message": "Data filtered out by business rules",
            }

        # Example: Limit the number of entities and relationships to prevent overwhelming the database
        max_entities = 50
        max_relationships = 100
        if len(filtered_entities) > max_entities:
            logger.warning(
                f"Truncating entities from {len(filtered_entities)} to {max_entities}"
            )
            filtered_entities = filtered_entities[:max_entities]
        if len(filtered_relationships) > max_relationships:
            logger.warning(
                f"Truncating relationships from {len(filtered_relationships)} to {max_relationships}"
            )
            filtered_relationships = filtered_relationships[:max_relationships]

        # Log the filtered data
        logger.info(
            f"Filtered data: {len(filtered_entities)} entities, {len(filtered_relationships)} relationships"
        )
        logger.debug(f"Filtered entities: {filtered_entities}")
        logger.debug(f"Filtered relationships: {filtered_relationships}")

        # Convert filtered data to dict for sending to Injector
        data_dict = {
            "entities": filtered_entities,
            "relationships": filtered_relationships,
            "summary": data.summary,
        }

        # Log the data being sent to the injector for debugging
        logger.debug(f"Data being sent to injector: {data_dict}")

        # Log before sending to Injector
        logger.info("Sending filtered data to Injector")
        logger.debug(f"Data to send: {data_dict}")

        # Check if injector_client is properly initialized
        if not hasattr(injector_client, "send_data_for_injection"):
            logger.error("injector_client does not have send_data_for_injection method")
            raise HTTPException(
                status_code=500, detail="Injector client not properly initialized"
            )

        # Check if send_data_for_injection is callable
        if not callable(getattr(injector_client, "send_data_for_injection", None)):
            logger.error("injector_client.send_data_for_injection is not callable")
            raise HTTPException(
                status_code=500, detail="Injector client method not callable"
            )

        # Send data to Injector for writing to Neo4j
        try:
            result = await injector_client.send_data_for_injection(data_dict)
            logger.debug(
                f"Result from injector_client.send_data_for_injection: {result}"
            )
            logger.debug(f"Result type: {type(result)}")
        except Exception as e:
            logger.error(
                f"Error calling injector_client.send_data_for_injection: {type(e).__name__}: {e}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Error calling injector: {type(e).__name__}: {e}",
            )

        # Log the result from Injector
        logger.info(f"Received response from Injector: {result}")
        logger.debug(f"Result type: {type(result)}")

        # Check if the result indicates success
        # The result structure has changed - success is now in node_data.success
        success = False
        if isinstance(result, dict):
            # Check the new structure first
            if "node_data" in result and isinstance(result["node_data"], dict):
                success = result["node_data"].get("success", False)
            # Fall back to the old structure
            else:
                success = result.get("success", False)

        if success:
            logger.info("Data successfully sent to Injector")
            return {
                "status": "processed",
                "message": "Data sent to Injector successfully",
            }
        else:
            # Extract error message from the new structure first
            error_msg = "Unknown error"
            if isinstance(result, dict):
                if "node_data" in result and isinstance(result["node_data"], dict):
                    error_msg = result["node_data"].get("error", "Unknown error")
                else:
                    error_msg = result.get("error", "Unknown error")

            logger.debug(f"error_msg: {error_msg}, type: {type(error_msg)}")
            # Check if error_msg is callable (it shouldn't be)
            if callable(error_msg):
                logger.error("error_msg is callable, which is unexpected")
                raise HTTPException(status_code=500, detail="error_msg is callable")
            logger.error(f"Failed to send data to Injector: {error_msg}")
            raise HTTPException(
                status_code=500, detail=f"Failed to inject data: {error_msg}"
            )
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
                    logger.error(
                        f"Object {obj_str} might be accidentally called as a function"
                    )
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {error_str}"
        )


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
                        logger.warning(
                            f"Failed to process truncated cache entry: {key}"
                        )

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
            logger.error(
                f"Distiller processing failed for {key}: {distiller_result['error']}"
            )
            return False

        logger.info(f"Distiller processing successful for {key}")
        logger.debug(f"Distiller result: {distiller_result}")
        logger.debug(f"Distiller result type: {type(distiller_result)}")

        # Step 2: Send to Injector for database storage
        # Transform and filter entities - convert Distiller format to Injector format and add IDs
        filtered_entities = []
        if "entities" in distiller_result:
            for i, entity in enumerate(distiller_result["entities"]):
                # Transform entity from Distiller format to Injector format
                # Distiller format: {"text": "...", "label": "...", "description": "..."}
                # Injector format: {"id": "...", "type": "...", "properties": {...}}
                entity_text = entity.get("text", "")
                entity_label = entity.get("label", "Entity")

                # Generate a more robust ID that handles edge cases
                if entity_text:
                    entity_id = f"entity_{i}_{abs(hash(entity_text))}"
                else:
                    entity_id = f"entity_{i}_no_text"

                transformed_entity = {
                    "id": entity_id,  # Generate ID based on index and text content
                    "type": entity_label,  # Use label as type
                    "properties": {
                        "name": entity_text,
                        "description": entity.get("description", ""),
                        "source_text": entity_text,
                    },
                }

                # Apply business rules for filtering
                # Example business rule: Only send entities with a 'name' property
                if transformed_entity["properties"].get("name"):
                    # Example business rule: Only send entities of certain types
                    # Include common spaCy entity types and our custom types
                    entity_type = transformed_entity.get("type", "")
                    if entity_type in [
                        "Concept",
                        "Person",
                        "PERSON",
                        "Organization",
                        "ORG",
                        "Event",
                        "EVENT",
                        "Product",
                        "PRODUCT",
                        "GPE",
                        "DATE",
                        "TIME",
                        "ENTITY",
                    ]:
                        filtered_entities.append(transformed_entity)

        # Transform and filter relationships - convert to expected format
        filtered_relationships = []
        if "relationships" in distiller_result:
            for i, relationship in enumerate(distiller_result["relationships"]):
                # Transform relationship to expected format
                # For now, we'll create a simple relationship structure
                # In a real implementation, the Distiller would provide more detailed relationship info
                transformed_relationship = {
                    "type": relationship.get("type", "RELATED_TO"),
                    "start_id": f"relationship_start_{i}",
                    "end_id": f"relationship_end_{i}",
                    "start_type": relationship.get("start_type", "Entity"),
                    "end_type": relationship.get("end_type", "Entity"),
                    "properties": relationship.get("properties", {}),
                }

                # Apply business rules for filtering
                # Example business rule: Only send relationships with a 'type' property
                if transformed_relationship.get("type"):
                    # Example business rule: Only send relationships of certain types
                    rel_type = transformed_relationship.get("type", "")
                    if rel_type in [
                        "RELATED_TO",
                        "PART_OF",
                        "CREATED_BY",
                        "WORKS_FOR",
                        "LOCATED_IN",
                    ]:
                        filtered_relationships.append(transformed_relationship)

        # Create properly structured data for the injector
        data_dict = {
            "entities": filtered_entities,
            "relationships": filtered_relationships,
            "summary": distiller_result.get("summary", ""),
        }

        logger.debug(f"Structured data for injector: {data_dict}")

        # Ensure all datetime objects are converted to strings before sending
        def convert_datetime_objects(obj):
            """Convert datetime objects to ISO format strings recursively."""
            if isinstance(obj, dict):
                return {k: convert_datetime_objects(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime_objects(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj

        sanitized_structured_data = convert_datetime_objects(data_dict)
        logger.debug(f"Sanitized structured data: {sanitized_structured_data}")
        injector_result = await injector_client.send_data_for_injection(
            sanitized_structured_data
        )

        # Check if the result indicates success
        # The result structure has changed - success is now in node_data.success
        success = False
        if isinstance(injector_result, dict):
            # Check the new structure first
            if "node_data" in injector_result and isinstance(
                injector_result["node_data"], dict
            ):
                success = injector_result["node_data"].get("success", False)
            # Fall back to the old structure
            else:
                success = injector_result.get("success", False)

        if not success:
            # Extract error message from the new structure first
            error_msg = "Unknown error"
            if isinstance(injector_result, dict):
                if "node_data" in injector_result and isinstance(
                    injector_result["node_data"], dict
                ):
                    error_msg = injector_result["node_data"].get(
                        "error", "Unknown error"
                    )
                else:
                    error_msg = injector_result.get("error", "Unknown error")

            logger.error(f"Injector processing failed for {key}: {error_msg}")
            return False

        logger.info(f"Injector processing successful for {key}")
        logger.debug(f"Injector result: {injector_result}")

        # Step 3: Refine relationships in the Q-Learning Agent
        # Use the transformed entity IDs for the path
        path = MemoryPath(nodes=[entity["id"] for entity in filtered_entities])
        await qlearning_client.refine_relationships(
            path, reward=1.0
        )  # Positive reward for successful processing

        # Step 4: Link to temporal spine if we have a memory node ID
        memory_node_id = injector_result.get("memory_node_id")
        timestamp = distiller_result.get("timestamp", datetime.now().isoformat())

        if memory_node_id:
            # Get or create the time node
            timenode_result = await injector_client.get_or_create_timenode(timestamp)

            if "error" not in timenode_result:
                # Link the memory to the time node
                link_success = await injector_client.link_memory_to_timenode(
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


async def _scan_cache_tail():
    """Scan the tail of the Redis cache for entries to archive."""
    try:
        # Get the current time
        current_time = time.time()

        # Get the last scan time from Redis
        last_scan_time_str = redis_client.get(last_scan_time_key)

        # If this is the first scan, set the last scan time to 1 hour ago
        if not last_scan_time_str:
            last_scan_time = current_time - 3600  # 1 hour ago
        else:
            last_scan_time = float(last_scan_time_str)

        # Calculate the time range for this scan (last 1 hour)
        scan_start_time = current_time - 3600  # 1 hour ago

        # Get all keys with the context_cache prefix
        all_keys = redis_client.keys("context_cache:*") or []

        if not all_keys:
            logger.debug("No cache entries found to process")
            # Update the last scan time
            redis_client.set(last_scan_time_key, str(current_time))
            return

        logger.info(f"Found {len(all_keys)} cache entries to process")

        # Filter keys based on their creation time
        keys_to_process = []
        for key in all_keys:
            # Get the creation time from the key's metadata
            entry_data = redis_client.hgetall(key) or {}
            if entry_data and "created_at" in entry_data:
                try:
                    # Parse the creation time (assuming it's in ISO format)
                    created_at_str = entry_data["created_at"]
                    created_at = datetime.fromisoformat(created_at_str)
                    created_at_timestamp = created_at.timestamp()

                    # Check if the entry was created within the scan window
                    if scan_start_time <= created_at_timestamp <= last_scan_time:
                        keys_to_process.append(key)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse creation time for key {key}: {e}")
                    # If we can't parse the creation time, we'll process it if it's old enough
                    # This is a fallback mechanism
                    entry_ttl = redis_client.ttl(key)
                    if entry_ttl > 0 and entry_ttl < 300:  # Less than 5 minutes left
                        keys_to_process.append(key)

        logger.info(f"Found {len(keys_to_process)} entries to process from cache tail")

        # Process each entry
        for key in keys_to_process:
            try:
                # Extract the actual key name (remove prefix)
                actual_key = key.replace("context_cache:", "")

                # Get the value
                entry_data = redis_client.hgetall(key) or {}
                if not entry_data:
                    continue

                value = entry_data.get("value", "")
                if not value:
                    continue

                # Process the entry
                success = await _process_cache_entry(actual_key, value)

                if not success:
                    logger.warning(f"Failed to process cache entry: {actual_key}")
            except Exception as e:
                logger.error(
                    f"Error processing cache entry {key}: {str(e)}", exc_info=True
                )

        # Update the last scan time
        redis_client.set(last_scan_time_key, str(current_time))

    except redis.ConnectionError as e:
        logger.error(f"Redis connection error while scanning cache tail: {str(e)}")
        # Try to reconnect
        if not await _reconnect_redis():
            raise
    except redis.TimeoutError as e:
        logger.error(f"Redis timeout error while scanning cache tail: {str(e)}")
        # Try to reconnect
        if not await _reconnect_redis():
            raise
    except Exception as e:
        import traceback

        error_details = f"An unexpected error occurred: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        logger.error(error_details)
        print(error_details)


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
            logger.warning(
                f"Failed to connect to Redis (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Failed to connect to Redis after all retries")
                return

    # Main scanning loop
    while True:
        try:
            # Perform cache tailing scan
            await _scan_cache_tail()

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
            logger.warning(
                f"Failed to reconnect to Redis (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Failed to reconnect to Redis after all retries")
                return False


@app.post("/memory_query")
async def memory_query(request: MemoryContextRequest):
    """
    Internal endpoint to handle memory queries from the Orchestrator for the Cohesion Loop.

    Args:
        request: MemoryContextRequest containing context_id and max_contexts

    Returns:
        List of relevant memory contexts
    """
    try:
        logger.info(
            f"Received memory query for context_id: {request.context_id} with max_contexts: {request.max_contexts}"
        )

        # Validate max_contexts to prevent memory bloat
        if request.max_contexts < 1 or request.max_contexts > 20:
            raise HTTPException(
                status_code=400, detail="max_contexts must be between 1 and 20"
            )

        # TODO: In a real implementation, query the QLearningAgent for relevant memories
        # This would involve:
        # 1. Looking up the context_id in the knowledge graph
        # 2. Finding related memories using the QLearningAgent
        # 3. Limiting results to max_contexts

        # Placeholder implementation - in a real system, this would query the knowledge graph
        related_memories = [
            {
                "memory_id": f"memory_{i}",
                "context_id": request.context_id,
                "content": f"Related memory content {i} for context {request.context_id}",
                "timestamp": datetime.now().isoformat(),
                "relevance_score": 1.0 - (i * 0.1),  # Decreasing relevance
            }
            for i in range(min(request.max_contexts, 5))  # Limit to max_contexts
        ]

        logger.info(f"Returning {len(related_memories)} related memories")
        return related_memories

    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error processing memory query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


class MemoryQueryRequest(BaseModel):
    """Model for memory query requests."""

    query: str


@app.post("/query_memory")
async def query_memory(request: MemoryQueryRequest):
    """
    Endpoint to query the knowledge graph for relevant memory/context.

    Args:
        request: MemoryQueryRequest containing the query

    Returns:
        String containing relevant context from the knowledge graph
    """
    try:
        query = request.query
        logger.info(f"Received query_memory request for query: {query[:100]}...")

        # Parse the query to identify relevant concepts for QLearning agent
        # This is a simple keyword extraction approach - in a more advanced implementation,
        # we'd use NLP to identify entities and concepts
        import re

        # Extract key terms from the query
        key_terms = re.findall(r"\b\w+\b", query.lower())
        # Use the first and last significant terms as start and end nodes for the path
        if len(key_terms) >= 2:
            start_node = key_terms[0]
            end_node = key_terms[-1]
        else:
            # If not enough terms, use the entire query or first term and a general concept
            start_node = key_terms[0] if key_terms else "unknown"
            end_node = "general_concept"

        # Call QLearningAgent to find optimal paths in the knowledge graph
        logger.info(
            f"Querying QLearning Agent for path from '{start_node}' to '{end_node}'"
        )
        paths = await qlearning_client.find_optimal_path(start_node, end_node)

        # Process the paths to extract relevant context
        if paths:
            # Get the highest-scoring path
            best_path = max(paths, key=lambda p: p.score if p.score is not None else 0)

            # Build context from the path
            path_context = f"Relevant context for query: '{query}'\n\n"
            path_context += (
                f"Found optimal path using QLearning: {start_node} -> {end_node}\n"
            )
            path_context += f"Path score: {best_path.score}\n"
            path_context += f"Path length: {best_path.length}\n"
            path_context += f"Nodes in path: {', '.join(best_path.nodes[:10])}{'...' if len(best_path.nodes) > 10 else ''}\n"

            # Add relationship details if available
            if best_path.relationships:
                path_context += f"Relationships: {len(best_path.relationships)}\n"
                for i, rel in enumerate(
                    best_path.relationships[:3]
                ):  # Limit to first 3 for brevity
                    path_context += f"  Relationship {i + 1}: {rel}\n"
                if len(best_path.relationships) > 3:
                    path_context += (
                        f"  ... and {len(best_path.relationships) - 3} more\n"
                    )

            logger.info(
                f"Returning {len(path_context)} characters of context from QLearning path"
            )
            return {"context": path_context}
        else:
            # If no paths found, return a more meaningful context
            context = f"Relevant context for query: '{query}'\n\n"
            context += (
                "No specific QLearning paths found in knowledge graph. "
                "This may indicate the concept is new or not yet connected in the knowledge graph.\n"
            )

            logger.info(
                f"Returning {len(context)} characters of context (no QLearning paths found)"
            )
            return {"context": context}

    except Exception as e:
        logger.error(f"Error processing query_memory request: {str(e)}", exc_info=True)
        # Return a meaningful error context instead of throwing HTTP exception
        error_context = (
            f"Relevant context for query: '{query}'\n\n"
            f"Error occurred while retrieving context: {str(e)}\n"
            f"System is attempting to continue with available information."
        )
        return {"context": error_context}


@app.get("/utcp")
async def utcp_manual():
    """UTCP Manual endpoint for tool discovery."""
    # Create UTCP Manual with tools provided by this agent
    manual = UtcpManual(
        manual_version="1.0.0",
        utcp_version="1.0.2",
        tools=[
            Tool(
                name="get_context",
                description="Get context based on query and keywords",
                tags=["retrieval", "context", "archivist"],
                inputs={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query to search for context",
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keywords to refine the search",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "The session ID for the request",
                        },
                    },
                    "required": ["query", "keywords"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "context": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path_id": {"type": "integer"},
                                    "nodes": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "relationships": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    },
                                    "relevance_score": {"type": "number"},
                                },
                            },
                        },
                        "metadata": {"type": "object"},
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="archivist_get_context",
                    call_template_type="http",
                    url="http://localhost:8003/context",
                    http_method="POST",
                ),
            ),
            Tool(
                name="get_enhanced_context",
                description="Get enhanced context with QLearning coordination",
                tags=["retrieval", "context", "enhanced", "archivist"],
                inputs={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query to search for context",
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keywords to refine the search",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Maximum number of tokens to return",
                            "default": 1000000,
                        },
                        "session_id": {
                            "type": "string",
                            "description": "The session ID for the request",
                        },
                    },
                    "required": ["query", "keywords", "max_tokens", "session_id"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "enhanced_context": {
                            "type": "string",
                            "description": "The enhanced context retrieved",
                        },
                        "related_memories": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "content": {"type": "string"},
                                    "relevance_score": {"type": "number"},
                                },
                            },
                        },
                        "token_count": {
                            "type": "integer",
                            "description": "Number of tokens in the enhanced context",
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="archivist_get_enhanced_context",
                    call_template_type="http",
                    url="http://localhost:8003/enhanced_context",
                    http_method="POST",
                ),
            ),
            Tool(
                name="memory_query",
                description="Query memory for related information in the cohesion loop",
                tags=["retrieval", "memory", "query", "archivist"],
                inputs={
                    "type": "object",
                    "properties": {
                        "context_id": {
                            "type": "string",
                            "description": "The context ID to query",
                        },
                        "max_contexts": {
                            "type": "integer",
                            "description": "Maximum number of contexts to retrieve",
                            "default": 5,
                        },
                    },
                    "required": ["context_id"],
                },
                outputs={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "memory_id": {"type": "string"},
                            "context_id": {"type": "string"},
                            "content": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "relevance_score": {"type": "number"},
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="archivist_memory_query",
                    call_template_type="http",
                    url="http://localhost:8003/memory_query",
                    http_method="POST",
                ),
            ),
        ],
    )
    return manual


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
        "archivist_agent:app", host="0.0.0.0", port=8003, reload=True, log_level="info"
    )

# --- Enhanced Context Endpoint Implementation ---


@app.post("/enhanced_context", response_model=EnhancedContextResponse)
async def get_enhanced_context(request: EnhancedContextRequest):
    """
    Enhanced endpoint that coordinates with QLearning Agent to provide context-aware responses (v3.1 Universal Context Retrieval Flow).

    This endpoint receives a query and coordinates with the QLearning Agent to:
    1. Find optimal paths through the knowledge graph (Graph Query)
    2. Build enhanced context from the paths (Context Summarization, up to 1M token limit)
    3. Retrieve related memories from the knowledge graph
    4. Store the enhanced context in Redis for other agents
    5. Return the enhanced context and related memories (Context Injection)

    Args:
        request: EnhancedContextRequest containing query, keywords, and limits

    Returns:
        EnhancedContextResponse with enhanced context and related memories
    """
    try:
        query = request.query
        keywords = request.keywords
        max_tokens = request.max_tokens
        session_id = request.session_id or "default"
        max_contexts = request.max_contexts

        logger.info(f"Received enhanced context request for query: {query[:100]}...")
        logger.info(
            f"Keywords: {keywords}, Max tokens: {max_tokens}, Session ID: {session_id}"
        )

        # Step 1: Extract keywords from query if not provided
        if not keywords:
            keywords = await _extract_keywords_from_query(query)
            logger.info(f"Extracted keywords: {keywords}")

        if not keywords:
            logger.warning("No keywords found in query")
            # Return minimal context
            minimal_context = f"No relevant context found for query: {query}"
            # Store in Redis for other agents
            context_key = f"context_cache:{session_id}:enhanced"
            redis_client.hset(context_key, "value", minimal_context)
            redis_client.hset(context_key, "created_at", datetime.now().isoformat())
            redis_client.expire(context_key, 3600)  # Expire in 1 hour

            return EnhancedContextResponse(
                enhanced_context=minimal_context,
                related_memories=[],
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                token_count=len(minimal_context.split()),
            )

        # Step 2: Query QLearning Agent for optimal paths (Graph Query)
        logger.info(
            f"Querying QLearning Agent for paths related to keywords: {keywords}"
        )
        if keywords and len(keywords) >= 2:
            start_node = keywords[0]
            end_node = keywords[-1]
        else:
            # If not enough keywords, use the first keyword as start and a generic concept as end
            start_node = keywords[0] if keywords else "concept_start"
            end_node = "concept_end"
        paths = await qlearning_client.find_optimal_path(start_node, end_node)
        logger.info(
            f"Retrieved {len(paths) if paths else 0} paths from QLearning Agent"
        )

        # Step 3: Build enhanced context from paths (Context Summarization)
        logger.info(f"Building enhanced context with max {max_tokens} tokens")

        if not paths:
            enhanced_context = "No related context paths found by QLearning Agent."
        else:
            context_parts = []
            total_tokens = 0

            # Process each path to build context
            for i, path in enumerate(paths[:10]):  # Limit to top 10 paths
                if total_tokens >= max_tokens:
                    logger.info(f"Reached token limit with {len(paths)} paths")
                    break

                # Extract information from the path
                path_info = f"n--- Context Path {i + 1} ---\n"

                if hasattr(path, "nodes") and path.nodes:
                    # Limit nodes for brevity (first 5 nodes)
                    node_names = (
                        path.nodes[:5]
                        if isinstance(path.nodes, list)
                        else [str(path.nodes)[:100]]
                    )
                    path_info += f"Nodes: {', '.join(node_names)}\n"

                if hasattr(path, "relationships") and path.relationships:
                    # Extract relationship types
                    if isinstance(path.relationships, list):
                        rel_types = list(
                            set(
                                [
                                    rel.get("type", "RELATED_TO")
                                    for rel in path.relationships[:3]
                                ]
                            )
                        )
                        path_info += f"Relationships: {', '.join(rel_types)}\n"
                    else:
                        path_info += f"Relationships: {str(path.relationships)[:100]}\n"

                if hasattr(path, "score"):
                    path_info += f"Relevance Score: {path.score:.2f}\n"

                if hasattr(path, "length"):
                    path_info += f"Path Length: {path.length}\n"

                # Estimate token count (rough approximation - 1.3 tokens per word)
                word_count = len(path_info.split())
                path_tokens = int(word_count * 1.3)

                if total_tokens + path_tokens <= max_tokens:
                    context_parts.append(path_info)
                    total_tokens += path_tokens
                else:
                    # Add partial context if we're near the limit
                    remaining_tokens = max_tokens - total_tokens
                    if remaining_tokens > 100:  # Only add if we have meaningful space
                        # Truncate the path info to fit within remaining tokens
                        chars_per_token = (
                            len(path_info) / path_tokens if path_tokens > 0 else 1
                        )
                        max_chars = int(
                            remaining_tokens * chars_per_token * 0.8
                        )  # 80% to be safe
                        truncated_info = path_info[:max_chars] + "... [truncated]"
                        context_parts.append(truncated_info)
                    break

            # Combine all context parts
            enhanced_context = "n".join(context_parts)

            # Add a summary at the beginning
            summary = f"Enhanced Context Summary (Generated from {len(context_parts)} knowledge paths):\n"
            summary += f"Total Context Length: ~{total_tokens} tokens\n"
            summary += "This context was retrieved and summarized by the QLearning Agent based on your query.\n"
            summary += "--- BEGIN CONTEXT ---\n"

            enhanced_context = summary + enhanced_context + "n--- END CONTEXT ---"

        token_count = len(enhanced_context.split())  # Rough token count
        logger.info(f"Enhanced context built ({token_count} tokens)")

        # Step 4: Get related memories from the knowledge graph
        logger.info(f"Retrieving related memories (max {max_contexts} contexts)")
        related_memories = []

        # In a real implementation, this would query the Neo4j database
        # For now, we'll create placeholder memories based on keywords
        for i, keyword in enumerate(keywords[:max_contexts]):
            memory = {
                "id": f"memory_{i}",
                "content": f"Related memory content for keyword '{keyword}'",
                "relevance_score": 1.0 - (i * 0.1),  # Decreasing relevance
                "timestamp": datetime.now().isoformat(),
                "keywords": [keyword],
            }
            related_memories.append(memory)

        logger.info(f"Retrieved {len(related_memories)} related memories")

        # Step 5: Store the enhanced context in Redis for other agents
        logger.info(
            f"Storing enhanced context in Redis cache for session: {session_id}"
        )
        context_key = f"context_cache:{session_id}:enhanced"
        redis_client.hset(context_key, "value", enhanced_context)
        redis_client.hset(context_key, "created_at", datetime.now().isoformat())
        redis_client.expire(context_key, 3600)  # Expire in 1 hour

        # Store related memories if any
        if related_memories:
            memories_key = f"context_cache:{session_id}:related_memories"
            memories_str = "n".join(
                [mem.get("content", "") for mem in related_memories]
            )
            redis_client.hset(memories_key, "value", memories_str)
            redis_client.hset(memories_key, "created_at", datetime.now().isoformat())
            redis_client.expire(memories_key, 3600)  # Expire in 1 hour

        logger.info(
            f"Enhanced context stored in Redis with keys: {context_key}, {memories_key if related_memories else 'no memories'}"
        )

        # Step 6: Return the enhanced context and related memories (Context Injection)
        logger.info("Returning enhanced context response")

        return EnhancedContextResponse(
            enhanced_context=enhanced_context,
            related_memories=related_memories,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            token_count=token_count,
        )

    except Exception as e:
        logger.error(
            f"Error processing enhanced context request: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def _extract_keywords_from_query(query: str) -> List[str]:
    """Extract keywords from a query using simple NLP techniques."""
    import re

    # Split text into words and filter out common stop words
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "was",
        "were",
        "are",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "can",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "what",
        "who",
        "when",
        "where",
        "why",
        "how",
    }
    words = re.findall(r"\b\w+\b", query.lower())
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    return list(set(keywords))[:20]  # Return unique keywords, limit to 20


class QueryMemoryRequest(BaseModel):
    """Model for query memory requests."""

    query: str


@app.post("/query_memory")
async def query_memory(request: QueryMemoryRequest):
    """
    Endpoint to query the knowledge graph for relevant memory/context.

    Args:
        request: QueryMemoryRequest containing the query

    Returns:
        Dictionary with context string containing relevant context from the knowledge graph
    """
    try:
        query = request.query
        logger.info(f"Received query_memory request for query: {query[:100]}...")

        # Parse the query to identify relevant concepts for QLearning agent
        # This is a simple keyword extraction approach - in a more advanced implementation,
        # we'd use NLP to identify entities and concepts
        import re

        # Extract key terms from the query
        key_terms = re.findall(r"\b\w+\b", query.lower())
        # Use the first and last significant terms as start and end nodes for the path
        if len(key_terms) >= 2:
            start_node = key_terms[0]
            end_node = key_terms[-1]
        else:
            # If not enough terms, use the entire query or first term and a general concept
            start_node = key_terms[0] if key_terms else "unknown"
            end_node = "general_concept"

        # Call QLearningAgent to find optimal paths in the knowledge graph
        logger.info(
            f"Querying QLearning Agent for path from '{start_node}' to '{end_node}'"
        )
        paths = await qlearning_client.find_optimal_path(start_node, end_node)

        # Process the paths to extract relevant context
        if paths:
            # Get the highest-scoring path
            best_path = max(paths, key=lambda p: p.score if p.score is not None else 0)

            # Build context from the path
            path_context = f"Relevant context for query: '{query}'\n\n"
            path_context += (
                f"Found optimal path using QLearning: {start_node} -> {end_node}\n"
            )
            path_context += f"Path score: {best_path.score}\n"
            path_context += f"Path length: {best_path.length}\n"
            path_context += f"Nodes in path: {', '.join(best_path.nodes[:10])}{'...' if len(best_path.nodes) > 10 else ''}\n"

            # Add relationship details if available
            if best_path.relationships:
                path_context += f"Relationships: {len(best_path.relationships)}\n"
                for i, rel in enumerate(
                    best_path.relationships[:3]
                ):  # Limit to first 3 for brevity
                    path_context += f"  Relationship {i + 1}: {rel}\n"
                if len(best_path.relationships) > 3:
                    path_context += (
                        f"  ... and {len(best_path.relationships) - 3} more\n"
                    )

            logger.info(
                f"Returning {len(path_context)} characters of context from QLearning path"
            )
            return {"context": path_context}
        else:
            # If no paths found, return a more meaningful context
            context = f"Relevant context for query: '{query}'\n\n"
            context += (
                "No specific QLearning paths found in knowledge graph. "
                "This may indicate the concept is new or not yet connected in the knowledge graph.\n"
            )

            logger.info(
                f"Returning {len(context)} characters of context (no QLearning paths found)"
            )
            return {"context": context}

    except Exception as e:
        logger.error(f"Error processing query_memory request: {str(e)}", exc_info=True)
        # Return a meaningful error context instead of throwing HTTP exception
        error_context = (
            f"Relevant context for query: '{query}'\n\n"
            f"Error occurred while retrieving context: {str(e)}\n"
            f"System is attempting to continue with available information."
        )
        return {"context": error_context}
