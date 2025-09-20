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

from .injector_agent import InjectorAgent
from ece.common.poml_schemas import POML, MemoryNode

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ECE Injector Agent",
    description="The Injector is a simple, specialized Tier 3 agent whose sole responsibility is to write data to the Neo4j knowledge graph.",
    version="1.0.0"
)

# Get Neo4j connection details from environment variables, with defaults for local development
neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')

# Create an instance of the injector agent
injector_agent = InjectorAgent(
    neo4j_uri=neo4j_uri,
    neo4j_user=neo4j_user,
    neo4j_password=neo4j_password
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
async def receive_data_for_injection(poml_request: POML):
    """
    Internal endpoint to receive structured data from the Archivist for injection into Neo4j.
    
    Args:
        poml_request: POML document containing the data to be injected.
        
    Returns:
        Status of data injection
    """
    try:
        logger.info(f"Received POML data for injection")
        
        # Extract data from the POML document
        data = poml_request.directive.task.get("data", {})
        
        # Log the incoming data (at debug level to avoid logging sensitive information in production)
        logger.debug(f"Received POML data for injection: {type(data)}")
        logger.debug(f"Data content: {data}")
        
        # Check if injector_agent is properly initialized
        if not hasattr(injector_agent, 'receive_data_for_injection'):
            logger.error("injector_agent does not have receive_data_for_injection method")
            raise HTTPException(status_code=500, detail="Injector agent not properly initialized")
        
        # Check if receive_data_for_injection is callable
        if not callable(getattr(injector_agent, 'receive_data_for_injection', None)):
            logger.error("injector_agent.receive_data_for_injection is not callable")
            raise HTTPException(status_code=500, detail="Injector agent method not callable")
        
        # Call the injector agent to process the data
        logger.info("Calling injector_agent.receive_data_for_injection")
        result = injector_agent.receive_data_for_injection(data)
        logger.info(f"Received result from injector_agent: {result}")
        logger.debug(f"Result type: {type(result)}")
        
        # Check if result is a dict
        if not isinstance(result, dict):
            logger.error(f"Expected dict from injector_agent.receive_data_for_injection, got {type(result)}: {result}")
            raise HTTPException(status_code=500, detail=f"Unexpected result type from injector agent: {type(result)}")
        
        if result.get("success"):
            logger.info("Data successfully injected")
            # Return a POML response
            response_poml = MemoryNode(
                identity={
                    "name": "InjectorAgent",
                    "version": "1.0",
                    "type": "Specialized Data Injection Agent"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Inject data into the Neo4j knowledge graph."
                },
                directive={
                    "goal": "Provide status of data injection operation.",
                    "task": {
                        "name": "InjectData",
                        "steps": [
                            "Receive data from Archivist",
                            "Translate data to Cypher queries",
                            "Execute queries in transaction"
                        ]
                    }
                },
                node_data=result,
                node_type="InjectionResult"
            )
            return response_poml.dict()
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.debug(f"error_msg: {error_msg}, type: {type(error_msg)}")
            # Check if error_msg is callable (it shouldn't be)
            if callable(error_msg):
                logger.error("error_msg is callable, which is unexpected")
                raise HTTPException(status_code=500, detail="error_msg is callable")
            logger.error(f"Failed to inject data: {error_msg}")
            # Create an error response in POML format
            error_response = MemoryNode(
                identity={
                    "name": "InjectorAgent",
                    "version": "1.0",
                    "type": "Specialized Data Injection Agent"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Inject data into the Neo4j knowledge graph."
                },
                directive={
                    "goal": "Provide status of data injection operation.",
                    "task": {
                        "name": "InjectData",
                        "steps": [
                            "Receive data from Archivist",
                            "Translate data to Cypher queries",
                            "Execute queries in transaction"
                        ]
                    }
                },
                node_data={
                    "success": False,
                    "error": error_msg
                },
                node_type="InjectionError"
            )
            return error_response.dict()
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
        # Create an error response in POML format
        error_response = MemoryNode(
            identity={
                "name": "InjectorAgent",
                "version": "1.0",
                "type": "Specialized Data Injection Agent"
            },
            operational_context={
                "project": "External Context Engine (ECE) v3.0",
                "objective": "Inject data into the Neo4j knowledge graph."
            },
            directive={
                "goal": "Provide status of data injection operation.",
                "task": {
                    "name": "InjectData",
                    "steps": [
                        "Receive data from Archivist",
                        "Translate data to Cypher queries",
                        "Execute queries in transaction"
                    ]
                }
            },
            node_data={
                "success": False,
                "error": error_str
            },
            node_type="InjectionError"
        )
        return error_response.dict()

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
        logger.info(f"Received request to create time node for timestamp: {request.timestamp}")
        
        # Call the injector agent to process the request
        result = injector_agent.get_or_create_timenode(request.timestamp)
        
        if result.get("success"):
            logger.info("Time node created successfully")
            # Return a POML response
            response_poml = MemoryNode(
                identity={
                    "name": "InjectorAgent",
                    "version": "1.0",
                    "type": "Specialized Data Injection Agent"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Inject data into the Neo4j knowledge graph."
                },
                directive={
                    "goal": "Provide status of temporal node creation operation.",
                    "task": {
                        "name": "CreateTimeNode",
                        "steps": [
                            "Receive timestamp from Archivist",
                            "Create chronological tree of nodes",
                            "Return time node information"
                        ]
                    }
                },
                node_data=result.get("time_node", {}),
                node_type="TemporalNodeResult"
            )
            return response_poml.dict()
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Failed to create time node: {error_msg}")
            # Create an error response in POML format
            error_response = MemoryNode(
                identity={
                    "name": "InjectorAgent",
                    "version": "1.0",
                    "type": "Specialized Data Injection Agent"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Inject data into the Neo4j knowledge graph."
                },
                directive={
                    "goal": "Provide status of temporal node creation operation.",
                    "task": {
                        "name": "CreateTimeNode",
                        "steps": [
                            "Receive timestamp from Archivist",
                            "Create chronological tree of nodes",
                            "Return time node information"
                        ]
                    }
                },
                node_data={
                    "success": False,
                    "error": error_msg
                },
                node_type="TemporalNodeError"
            )
            return error_response.dict()
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error processing time node request: {str(e)}", exc_info=True)
        # Create an error response in POML format
        error_response = MemoryNode(
            identity={
                "name": "InjectorAgent",
                "version": "1.0",
                "type": "Specialized Data Injection Agent"
            },
            operational_context={
                "project": "External Context Engine (ECE) v3.0",
                "objective": "Inject data into the Neo4j knowledge graph."
            },
            directive={
                "goal": "Provide status of temporal node creation operation.",
                "task": {
                    "name": "CreateTimeNode",
                    "steps": [
                        "Receive timestamp from Archivist",
                        "Create chronological tree of nodes",
                        "Return time node information"
                    ]
                }
            },
            node_data={
                "success": False,
                "error": str(e)
            },
            node_type="TemporalNodeError"
        )
        return error_response.dict()

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
        logger.info(f"Received request to link memory {request.memory_node_id} to time node for timestamp: {request.timestamp}")
        
        # Call the injector agent to process the request
        result = injector_agent.link_memory_to_timenode(request.memory_node_id, request.timestamp)
        
        if result.get("success"):
            logger.info("Memory node linked to time node successfully")
            # Return a POML response
            response_poml = MemoryNode(
                identity={
                    "name": "InjectorAgent",
                    "version": "1.0",
                    "type": "Specialized Data Injection Agent"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Inject data into the Neo4j knowledge graph."
                },
                directive={
                    "goal": "Provide status of memory linking operation.",
                    "task": {
                        "name": "LinkMemoryToTimeNode",
                        "steps": [
                            "Receive memory node ID and timestamp from Archivist",
                            "Link memory node to temporal node",
                            "Return operation status"
                        ]
                    }
                },
                node_data=result,
                node_type="LinkMemoryResult"
            )
            return response_poml.dict()
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Failed to link memory node to time node: {error_msg}")
            # Create an error response in POML format
            error_response = MemoryNode(
                identity={
                    "name": "InjectorAgent",
                    "version": "1.0",
                    "type": "Specialized Data Injection Agent"
                },
                operational_context={
                    "project": "External Context Engine (ECE) v3.0",
                    "objective": "Inject data into the Neo4j knowledge graph."
                },
                directive={
                    "goal": "Provide status of memory linking operation.",
                    "task": {
                        "name": "LinkMemoryToTimeNode",
                        "steps": [
                            "Receive memory node ID and timestamp from Archivist",
                            "Link memory node to temporal node",
                            "Return operation status"
                        ]
                    }
                },
                node_data={
                    "success": False,
                    "error": error_msg
                },
                node_type="LinkMemoryError"
            )
            return error_response.dict()
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        logger.error(f"Error processing memory link request: {str(e)}", exc_info=True)
        # Create an error response in POML format
        error_response = MemoryNode(
            identity={
                "name": "InjectorAgent",
                "version": "1.0",
                "type": "Specialized Data Injection Agent"
            },
            operational_context={
                "project": "External Context Engine (ECE) v3.0",
                "objective": "Inject data into the Neo4j knowledge graph."
            },
            directive={
                "goal": "Provide status of memory linking operation.",
                "task": {
                    "name": "LinkMemoryToTimeNode",
                    "steps": [
                        "Receive memory node ID and timestamp from Archivist",
                        "Link memory node to temporal node",
                        "Return operation status"
                    ]
                }
            },
            node_data={
                "success": False,
                "error": str(e)
            },
            node_type="LinkMemoryError"
        )
        return error_response.dict()

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    injector_agent.neo4j_manager.disconnect()

if __name__ == "__main__":
    uvicorn.run(
        "injector_app:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )