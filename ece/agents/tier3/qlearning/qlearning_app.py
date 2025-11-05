import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import logging
import os
import sys

# Add the qlearning agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from qlearning_agent import QLearningGraphAgent, MemoryPath
from neo4j_manager import Neo4jManager

# Import UTCP data models for manual creation
from utcp.data.utcp_manual import UtcpManual
from utcp.data.tool import Tool
from utcp_http.http_call_template import HttpCallTemplate

# Import and set up ECE logging system
try:
    from ece.common.logging_config import get_logger

    logger = get_logger("qlearning")
except ImportError:
    # Fallback if logging config not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Could not import ECE logging system, using default logging")

# Initialize FastAPI app
app = FastAPI(
    title="ECE QLearning Agent",
    description="The QLearning is a simple, specialized Tier 3 agent whose sole responsibility is to find optimal paths between concepts in the Neo4j knowledge graph.",
    version="1.0.0",
)

# Get Neo4j connection details from environment variables, with defaults for local development
neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
neo4j_password = os.environ.get("NEO4J_PASSWORD", "ECE_secure_password_2025")

# Create an instance of the Neo4jManager and connect to the database
graph_manager = Neo4jManager(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)
graph_manager.connect()

# Create an instance of the qlearning agent
qlearning_agent = QLearningGraphAgent(
    graph_manager=graph_manager,
    config={
        "learning_rate": 0.1,
        "discount_factor": 0.9,
        "epsilon": 0.1,
    },
)


class PathRequest(BaseModel):
    """Model for path requests."""

    start_node: str
    end_node: str


class RefineRequest(BaseModel):
    """Model for refine requests."""

    path: Dict[str, Any]
    reward: float


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE QLearning Agent is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/find_optimal_path")
async def find_optimal_path(request: PathRequest):
    """
    Internal endpoint to find the optimal path between two nodes.

    Args:
        request: PathRequest containing start and end nodes

    Returns:
        List of MemoryPath objects ranked by Q-values
    """
    try:
        logger.info(
            f"Received request to find optimal path from {request.start_node} to {request.end_node}"
        )

        # Call the qlearning agent to process the request
        result = await qlearning_agent.find_optimal_path(
            request.start_node, request.end_node
        )

        return result
    except Exception as e:
        logger.error(f"Error processing path request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/refine_relationships")
async def refine_relationships(request: RefineRequest):
    """
    Internal endpoint to refine relationships based on a path and a reward.

    Args:
        request: RefineRequest containing the path and reward

    Returns:
        Status of the operation
    """
    try:
        logger.info(
            f"Received request to refine relationships with reward {request.reward}"
        )

        # Call the qlearning agent to process the request
        path = MemoryPath(**request.path)
        await qlearning_agent.refine_relationships(path, request.reward)

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing refine request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """
    Start the continuous training loop on startup.
    """
    await qlearning_agent.start_continuous_training()


@app.get("/utcp")
async def utcp_manual():
    """UTCP Manual endpoint for tool discovery."""
    # Create UTCP Manual with tools provided by this agent
    manual = UtcpManual(
        manual_version="1.0.0",
        utcp_version="1.0.2",
        tools=[
            Tool(
                name="find_optimal_path",
                description="Find the optimal path between two nodes in the knowledge graph",
                tags=["analysis", "qlearning", "pathfinding"],
                inputs={
                    "type": "object",
                    "properties": {
                        "start_node": {
                            "type": "string",
                            "description": "The starting node for the path",
                        },
                        "end_node": {
                            "type": "string",
                            "description": "The ending node for the path",
                        },
                    },
                    "required": ["start_node", "end_node"],
                },
                outputs={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nodes": {"type": "array", "items": {"type": "string"}},
                            "relationships": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "start_id": {"type": "string"},
                                        "end_id": {"type": "string"},
                                    },
                                },
                            },
                            "score": {"type": "number"},
                            "length": {"type": "integer"},
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="qlearning_find_optimal_path",
                    call_template_type="http",
                    url="http://localhost:8002/find_optimal_path",
                    http_method="POST",
                ),
            ),
            Tool(
                name="refine_relationships",
                description="Refine relationships based on a path and a reward",
                tags=["analysis", "qlearning", "refinement"],
                inputs={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "object",
                            "properties": {
                                "nodes": {"type": "array", "items": {"type": "string"}},
                                "relationships": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string"},
                                            "start_id": {"type": "string"},
                                            "end_id": {"type": "string"},
                                        },
                                    },
                                },
                                "score": {"type": "number"},
                                "length": {"type": "integer"},
                            },
                        },
                        "reward": {
                            "type": "number",
                            "description": "The reward value to apply",
                        },
                    },
                    "required": ["path", "reward"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Status of the operation",
                        }
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="qlearning_refine_relationships",
                    call_template_type="http",
                    url="http://localhost:8002/refine_relationships",
                    http_method="POST",
                ),
            ),
        ],
    )
    return manual


# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    if qlearning_agent.graph_manager:
        qlearning_agent.graph_manager.close()


if __name__ == "__main__":
    uvicorn.run(
        "qlearning_app:app", host="0.0.0.0", port=8002, reload=True, log_level="info"
    )
