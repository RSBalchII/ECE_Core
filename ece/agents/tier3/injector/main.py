"""
Main entry point for the Injector Agent
"""

import os
import sys
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn
import logging

# Add the injector agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from injector_agent import InjectorAgent
from ece.common.poml_schemas import POML, MemoryNode

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastAPI app
app = FastAPI(
    title="ECE Injector Agent",
    description="The Injector is responsible for writing data to the Neo4j knowledge graph.",
    version="1.0.0",
)

# Get Neo4j connection details from environment variables, with defaults for local development
neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
neo4j_password = os.environ.get("NEO4J_PASSWORD", "ECE_secure_password_2025")

# Create an instance of the injector agent
injector_agent = InjectorAgent(
    neo4j_uri=neo4j_uri, neo4j_user=neo4j_user, neo4j_password=neo4j_password
)


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE Injector Agent is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/internal/data_to_inject")
async def receive_data_for_injection(poml_request: POML):
    """
    Internal endpoint to receive data from the Archivist for injection into Neo4j.

    Args:
        poml_request: POML document containing the data to be injected.

    Returns:
        Result of the injection operation.
    """
    try:
        # Extract data from the POML document
        data = poml_request.directive.task.get("data", {})

        # Log the incoming data (at debug level to avoid logging sensitive information in production)
        logger.debug(f"Received POML data for injection: {type(data)}")
        logger.debug(f"Data content: {data}")

        # Inject the data
        result = injector_agent.receive_data_for_injection(data)

        # Create a POML response
        response_poml = MemoryNode(
            identity={
                "name": "InjectorAgent",
                "version": "1.0",
                "type": "Specialized Data Injection Agent",
            },
            operational_context={
                "project": "External Context Engine (ECE) v2.0",
                "objective": "Inject data into the Neo4j knowledge graph.",
            },
            directive={
                "goal": "Provide status of data injection operation.",
                "task": {
                    "name": "InjectData",
                    "steps": [
                        "Receive data from Archivist",
                        "Translate data to Cypher queries",
                        "Execute queries in transaction",
                    ],
                },
            },
            node_data=result,
            node_type="InjectionResult",
        )

        return response_poml.dict()
    except Exception as e:
        # Create an error response in POML format
        error_response = MemoryNode(
            identity={
                "name": "InjectorAgent",
                "version": "1.0",
                "type": "Specialized Data Injection Agent",
            },
            operational_context={
                "project": "External Context Engine (ECE) v2.0",
                "objective": "Inject data into the Neo4j knowledge graph.",
            },
            directive={
                "goal": "Provide status of data injection operation.",
                "task": {
                    "name": "InjectData",
                    "steps": [
                        "Receive data from Archivist",
                        "Translate data to Cypher queries",
                        "Execute queries in transaction",
                    ],
                },
            },
            node_data={"success": False, "error": str(e)},
            node_type="InjectionError",
        )
        return error_response.dict()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True, log_level="info")
