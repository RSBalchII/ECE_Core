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

# Import the CacheManager
from src.external_context_engine.tools.cache_manager import CacheManager

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

# Initialize CacheManager
cache_config = config.get('cache', {})
cache_manager = CacheManager(config=cache_config)
logger.info("CacheManager initialized")

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
        elif any(keyword in message.lower() for keyword in ["cache", "retrieve", "store in cache", "cached", "memory cache"]):
            intent = "cache_operation"
        
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
        elif intent == "cache_operation":
            # For cache operations, we need to get cache action and data from context
            cache_action = context.get("cache_action", "")
            cache_key = context.get("cache_key", "")
            cache_value = context.get("cache_value", "")
            cache_embedding = context.get("cache_embedding", None)
            
            if cache_action == "store" and cache_key and cache_value:
                result = await cache_manager.store(cache_key, cache_value, cache_embedding)
                if result:
                    response_text = f"Stored value in cache with key: {cache_key}"
                else:
                    response_text = f"Failed to store value in cache with key: {cache_key}"
                agent_used = "CacheManager"
            elif cache_action == "retrieve" and cache_key:
                result = await cache_manager.retrieve(cache_key)
                if result:
                    response_text = f"Retrieved value from cache: {result}"
                else:
                    response_text = f"No value found in cache for key: {cache_key}"
                agent_used = "CacheManager"
            else:
                response_text = "Please provide cache action (store/retrieve) and required data."
                agent_used = "CacheManager"
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

# Data models for CacheManager endpoints
from src.external_context_engine.tools.cache_manager import CacheEntry, SemanticQuery, CacheStats
from typing import List, Optional

class CacheStoreRequest(BaseModel):
    key: str
    value: str
    embedding: Optional[List[float]] = None
    ttl: Optional[int] = None

class CacheRetrieveRequest(BaseModel):
    key: str

class SemanticSearchRequest(BaseModel):
    query_embedding: List[float]
    threshold: float = 0.8

@app.post("/cache/store")
async def cache_store(store_request: CacheStoreRequest):
    """Store a value in the cache."""
    try:
        result = await cache_manager.store(
            store_request.key,
            store_request.value,
            store_request.embedding,
            store_request.ttl
        )
        return {"success": result}
    except Exception as e:
        logger.error(f"Error storing in cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/cache/retrieve")
async def cache_retrieve(retrieve_request: CacheRetrieveRequest):
    """Retrieve a value from the cache."""
    try:
        result = await cache_manager.retrieve(retrieve_request.key)
        return {"key": retrieve_request.key, "value": result}
    except Exception as e:
        logger.error(f"Error retrieving from cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/cache/semantic_search")
async def cache_semantic_search(search_request: SemanticSearchRequest):
    """Perform semantic search in the cache."""
    try:
        results = await cache_manager.semantic_search(
            search_request.query_embedding,
            search_request.threshold
        )
        return results
    except Exception as e:
        logger.error(f"Error performing semantic search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    try:
        stats = await cache_manager.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/cache/clear")
async def cache_clear():
    """Clear the cache."""
    try:
        result = await cache_manager.clear()
        return {"success": result}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
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