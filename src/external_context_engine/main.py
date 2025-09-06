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

class ChatMessage(BaseModel):
    message: str
    context: Dict[str, Any] = {}

class ChatResponse(BaseModel):
    response: str
    context: Dict[str, Any] = {}
    agent_used: str = ""

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)