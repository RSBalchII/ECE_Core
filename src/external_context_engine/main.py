"""
Main application for the External Context Engine
"""
import os
import sys
import yaml
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import our specialist agents
from src.external_context_engine.tools.specialist_agents import (
    WebSearchAgent,
    MultiModalIngestionAgent,
    CoherenceAgent,
    SafetyAgent
)

# Import the new ExtractorAgent
from src.external_context_engine.tools.extractor_agent import ExtractorAgent

# Import the ArchivistAgent
from src.external_context_engine.tools.archivist_agent import ArchivistAgent
from src.external_context_engine.utils.db_manager import Neo4jManager

# Import the QLearningGraphAgent
from src.external_context_engine.memory_management.q_learning.q_learning_agent import QLearningGraphAgent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="External Context Engine", version="1.0.0")

# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}

# Global variables for agents and config
config = load_config()
web_search_agent = WebSearchAgent(config.get('agents', {}).get('WebSearchAgent', {}))
multi_modal_agent = MultiModalIngestionAgent(config.get('agents', {}).get('MultiModalIngestionAgent', {}))
coherence_agent = CoherenceAgent(config.get('agents', {}).get('CoherenceAgent', {}))
safety_agent = SafetyAgent(config.get('agents', {}).get('SafetyAgent', {}))
extractor_agent = ExtractorAgent(config.get('agents', {}).get('ExtractorAgent', {}))

# Initialize Neo4j manager and ArchivistAgent
neo4j_config = config.get('agents', {}).get('ArchivistAgent', {})
neo4j_manager = Neo4jManager(
    uri=neo4j_config.get('neo4j_uri', 'bolt://localhost:7687'),
    user=neo4j_config.get('neo4j_user', 'neo4j'),
    password=neo4j_config.get('neo4j_password', 'password')
)
# Connect to Neo4j
try:
    neo4j_manager.connect()
    logger.info("Connected to Neo4j database")
except Exception as e:
    logger.error(f"Failed to connect to Neo4j database: {e}")

archivist_agent = ArchivistAgent(neo4j_manager=neo4j_manager)

# Initialize QLearningGraphAgent
q_learning_config = config.get('agents', {}).get('QLearningGraphAgent', {})
q_learning_agent = QLearningGraphAgent(graph_manager=neo4j_manager, config=q_learning_config)
# Initialize the agent asynchronously
try:
    import asyncio
    asyncio.run(q_learning_agent.initialize())
    logger.info("QLearningGraphAgent initialized")
except Exception as e:
    logger.error(f"Failed to initialize QLearningGraphAgent: {e}")

class ChatMessage(BaseModel):
    message: str
    context: Dict[str, Any] = {}

class ChatResponse(BaseModel):
    response: str
    context: Dict[str, Any] = {}
    agent_used: str = ""

# Data models for ArchivistAgent endpoints
from src.external_context_engine.tools.archivist_agent import Entity, Relationship, Query

# Data models for QLearningGraphAgent endpoints
from src.external_context_engine.memory_management.models.memory_path import MemoryPath
from typing import List, Tuple, Optional, Dict, Any

class FindPathsRequest(BaseModel):
    start_nodes: List[Dict[str, Any]]
    end_nodes: Optional[List[Dict[str, Any]]] = None
    max_hops: int = 5

class UpdateQValuesRequest(BaseModel):
    path: List[Any]
    reward: float

class TrainRequest(BaseModel):
    training_data: List[Tuple[str, str, float]]

class StoreRequest(BaseModel):
    data: list

class RetrieveRequest(BaseModel):
    query: Query

class UpdateRequest(BaseModel):
    item: Dict[str, Any]  # Could be Entity or Relationship

class DeleteRequest(BaseModel):
    id: str
    type: str

@app.get("/")
async def root():
    return {"message": "External Context Engine API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/chat")
async def chat(chat_message: ChatMessage):
    try:
        message = chat_message.message
        context = chat_message.context
        
        # Simple intent detection based on keywords
        intent = "web_search"  # default intent
        
        # Check for specific keywords to determine intent
        if any(keyword in message.lower() for keyword in ["image", "video", "document", "pdf", "media"]):
            intent = "multi_modal_processing"
        elif any(keyword in message.lower() for keyword in ["coherence", "consistency", "flow", "readability"]):
            intent = "coherence_check"
        elif any(keyword in message.lower() for keyword in ["safety", "appropriate", "filter", "moderation"]):
            intent = "safety_check"
        elif any(keyword in message.lower() for keyword in ["extract", "information", "data", "parse", "analyze"]):
            intent = "extract_information"
        elif any(keyword in message.lower() for keyword in ["archive", "store", "memory", "persist", "save"]):
            intent = "archive_memory"
        
        # Route to appropriate agent based on intent
        if intent == "web_search":
            result = await web_search_agent.execute(message)
            response_text = f"Web search results for '{message}': {len(result.get('results', []))} results found."
            agent_used = "WebSearchAgent"
        elif intent == "multi_modal_processing":
            result = await multi_modal_agent.execute(message, "text")
            response_text = f"Processed multi-modal content of type 'text'."
            agent_used = "MultiModalIngestionAgent"
        elif intent == "coherence_check":
            result = await coherence_agent.execute(context, message)
            response_text = f"Coherence score: {result.get('coherence_score', 0)}"
            agent_used = "CoherenceAgent"
        elif intent == "safety_check":
            result = await safety_agent.execute(message)
            response_text = f"Safety score: {result.get('safety_score', 0)}"
            agent_used = "SafetyAgent"
        elif intent == "extract_information":
            # For extraction, we need to get data source, type, and criteria from context
            data_source = context.get("data_source", "")
            data_type = context.get("data_type", "text")
            criteria = context.get("criteria", {})
            
            if data_source:
                result = await extractor_agent.execute(data_source, data_type, criteria)
                extracted_items = len(result.get("extracted_data", []))
                query_count = len(result.get("queries", []))
                response_text = f"Extracted {extracted_items} items and generated {query_count} queries."
                agent_used = "ExtractorAgent"
            else:
                response_text = "Please provide a data source for extraction."
                agent_used = "ExtractorAgent"
        elif intent == "archive_memory":
            # For archiving, we need to get structured data from context
            structured_data = context.get("structured_data", [])
            
            if structured_data:
                result = await archivist_agent.store(structured_data)
                stored_entities = result.get("stored_entities", 0)
                stored_relationships = result.get("stored_relationships", 0)
                response_text = f"Archived {stored_entities} entities and {stored_relationships} relationships."
                agent_used = "ArchivistAgent"
            else:
                response_text = "Please provide structured data for archiving."
                agent_used = "ArchivistAgent"
        else:
            # Default to web search
            result = await web_search_agent.execute(message)
            response_text = f"Web search results for '{message}': {len(result.get('results', []))} results found."
            agent_used = "WebSearchAgent"
        
        return ChatResponse(
            response=response_text,
            context=context,
            agent_used=agent_used
        )
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/archive/store")
async def store_data(store_request: StoreRequest):
    """Store entities and relationships in the knowledge graph."""
    try:
        # Convert the data to Entity and Relationship objects
        data_objects = []
        for item in store_request.data:
            if "start_entity_id" in item:
                # It's a relationship
                data_objects.append(Relationship(**item))
            else:
                # It's an entity
                data_objects.append(Entity(**item))
        
        result = await archivist_agent.store(data_objects)
        return result
    except Exception as e:
        logger.error(f"Error storing data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/archive/retrieve")
async def retrieve_data(retrieve_request: RetrieveRequest):
    """Retrieve information from the knowledge graph."""
    try:
        result = await archivist_agent.retrieve(retrieve_request.query)
        return result
    except Exception as e:
        logger.error(f"Error retrieving data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/archive/update")
async def update_data(update_request: UpdateRequest):
    """Update an entity or relationship in the knowledge graph."""
    try:
        # Convert the data to Entity or Relationship object
        item_data = update_request.item
        if "start_entity_id" in item_data:
            # It's a relationship
            item = Relationship(**item_data)
        else:
            # It's an entity
            item = Entity(**item_data)
        
        result = await archivist_agent.update(item)
        return result
    except Exception as e:
        logger.error(f"Error updating data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/archive/delete")
async def delete_data(delete_request: DeleteRequest):
    """Delete an entity or relationship from the knowledge graph."""
    try:
        result = await archivist_agent.delete(delete_request.id, delete_request.type)
        return result
    except Exception as e:
        logger.error(f"Error deleting data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# QLearningGraphAgent endpoints
@app.post("/q_learning/find_paths")
async def find_paths(find_paths_request: FindPathsRequest):
    """Find optimal paths using Q-values for guidance."""
    try:
        paths = await q_learning_agent.find_paths(
            find_paths_request.start_nodes,
            find_paths_request.end_nodes,
            find_paths_request.max_hops
        )
        return paths
    except Exception as e:
        logger.error(f"Error finding paths: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/q_learning/update_q_values")
async def update_q_values(update_q_values_request: UpdateQValuesRequest):
    """Update Q-values based on the success of a path."""
    try:
        await q_learning_agent.update_q_values(
            update_q_values_request.path,
            update_q_values_request.reward
        )
        return {"status": "success", "message": "Q-values updated"}
    except Exception as e:
        logger.error(f"Error updating Q-values: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/q_learning/train")
async def train(train_request: TrainRequest):
    """Train the Q-Learning agent with historical path data."""
    try:
        await q_learning_agent.train(train_request.training_data)
        return {"status": "success", "message": "Training completed"}
    except Exception as e:
        logger.error(f"Error during training: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/q_learning/convergence_metrics")
async def get_convergence_metrics():
    """Get metrics about Q-Learning convergence."""
    try:
        metrics = q_learning_agent.get_convergence_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Error getting convergence metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)