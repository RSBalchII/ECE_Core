"""
Injector Agent API Server
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import logging
import os
import sys

# Add the injector agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from injector_agent import InjectorAgent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ECE Injector Agent",
    description="The Injector is a simple, specialized Tier 3 agent whose sole responsibility is to write data to the Neo4j knowledge graph.",
    version="1.0.0",
)

# Get Neo4j connection details from environment variables, with defaults for local development
neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7688")
neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
neo4j_password = os.environ.get("NEO4J_PASSWORD", "ECE_secure_password_2025")

# Create an instance of the injector agent
injector_agent = InjectorAgent(
    neo4j_uri=neo4j_uri, neo4j_user=neo4j_user, neo4j_password=neo4j_password
)


class InjectionData(BaseModel):
    """Model for data to be injected into the Neo4j database."""

    entities: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []
    summary: str = ""


class TemporalNodeRequest(BaseModel):
    """Model for temporal node requests."""

    timestamp: str


class MemoryLinkRequest(BaseModel):
    """Model for linking memory to temporal nodes."""

    memory_node_id: int
    timestamp: str


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE Injector Agent is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/internal/data_to_inject")
async def receive_data_for_injection(data: InjectionData):
    """
    Internal endpoint to receive structured data from the Archivist for injection into Neo4j.

    Args:
        data: InjectionData containing entities, relationships, and summary

    Returns:
        Status of data injection
    """
    try:
        logger.info(
            f"Received data for injection: {len(data.entities)} entities, {len(data.relationships)} relationships"
        )

        # Convert InjectionData to dict for the injector agent
        data_dict = {
            "entities": data.entities,
            "relationships": data.relationships,
            "summary": data.summary,
        }

        # Log the data being sent to the injector agent
        logger.debug(f"Data to send to injector agent: {data_dict}")
        logger.debug(f"Data dict type: {type(data_dict)}")

        # Check if injector_agent is properly initialized
        if not hasattr(injector_agent, "receive_data_for_injection"):
            logger.error(
                "injector_agent does not have receive_data_for_injection method"
            )
            raise HTTPException(
                status_code=500, detail="Injector agent not properly initialized"
            )

        # Check if receive_data_for_injection is callable
        if not callable(getattr(injector_agent, "receive_data_for_injection", None)):
            logger.error("injector_agent.receive_data_for_injection is not callable")
            raise HTTPException(
                status_code=500, detail="Injector agent method not callable"
            )

        # Call the injector agent to process the data
        logger.info("Calling injector_agent.receive_data_for_injection")
        result = injector_agent.receive_data_for_injection(data_dict)
        logger.info(f"Received result from injector_agent: {result}")
        logger.debug(f"Result type: {type(result)}")

        # Check if result is a dict
        if not isinstance(result, dict):
            logger.error(
                f"Expected dict from injector_agent.receive_data_for_injection, got {type(result)}: {result}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected result type from injector agent: {type(result)}",
            )

        if result.get("success"):
            logger.info("Data successfully injected")
            return {"status": "processed", "message": "Data injected successfully"}
        else:
            error_msg = result.get("error", "Unknown error")
            logger.debug(f"error_msg: {error_msg}, type: {type(error_msg)}")
            # Check if error_msg is callable (it shouldn't be)
            if callable(error_msg):
                logger.error("error_msg is callable, which is unexpected")
                raise HTTPException(status_code=500, detail="error_msg is callable")
            logger.error(f"Failed to inject data: {error_msg}")
            raise HTTPException(
                status_code=500, detail=f"Failed to inject data: {error_msg}"
            )
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error processing injection data: {str(e)}", exc_info=True)
        error_str = str(e)
        logger.debug(f"error_str: {error_str}, type: {type(error_str)}")
        # Check if error_str is callable (it shouldn't be)
        if callable(error_str):
            logger.error("error_str is callable, which is unexpected")
            raise HTTPException(status_code=500, detail="error_str is callable")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {error_str}"
        )


@app.post("/internal/temporal/get_or_create_timenode")
async def get_or_create_timenode(request: TemporalNodeRequest):
    """
    Internal endpoint to create a chronological tree of nodes.

    Args:
        request: TemporalNodeRequest containing timestamp

    Returns:
        Day node information
    """
    try:
        logger.info(
            f"Received request to create time node for timestamp: {request.timestamp}"
        )

        # Call the injector agent to process the request
        result = injector_agent.get_or_create_timenode(request.timestamp)

        if result.get("success"):
            logger.info("Time node created successfully")
            return result.get("data", {})
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Failed to create time node: {error_msg}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create time node: {error_msg}"
            )
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error processing time node request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/internal/temporal/link_memory_to_timenode")
async def link_memory_to_timenode(request: MemoryLinkRequest):
    """
    Internal endpoint to link a memory node to a temporal node.

    Args:
        request: MemoryLinkRequest containing memory node ID and timestamp

    Returns:
        Status of the link operation
    """
    try:
        logger.info(
            f"Received request to link memory {request.memory_node_id} to time node for timestamp: {request.timestamp}"
        )

        # Call the injector agent to process the request
        result = injector_agent.link_memory_to_timenode(
            request.memory_node_id, request.timestamp
        )

        if result.get("success"):
            logger.info("Memory node linked to time node successfully")
            return {
                "success": True,
                "message": "Memory node linked to time node successfully",
            }
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Failed to link memory node to time node: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to link memory node to time node: {error_msg}",
            )
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error processing memory link request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    injector_agent.db_manager.disconnect()


if __name__ == "__main__":
    uvicorn.run(
        "injector_api:app", host="0.0.0.0", port=8004, reload=True, log_level="info"
    )
