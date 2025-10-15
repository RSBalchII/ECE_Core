"""
Web Search Agent App for the External Context Engine (ECE) v2.0 (Async).

This module implements the FastAPI app for the Web Search agent using a fully
asynchronous model to align with the ECE architecture and enable non-blocking I/O.
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

# Import the WebSearchAgent
from ece.agents.tier2.web_search_agent import WebSearchAgent

# Import UTCP data models for manual creation
from utcp.data.utcp_manual import UtcpManual
from utcp.data.tool import Tool
from utcp_http.http_call_template import HttpCallTemplate

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ECE Web Search Agent",
    description="The WebSearchAgent provides web search capabilities for the ECE.",
    version="1.0.0"
)

# Get Tavily API key from environment variables
tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key:
    logger.warning("TAVILY_API_KEY not found in environment variables. Web search functionality will be limited.")

# Create an instance of the WebSearchAgent
web_search_agent = WebSearchAgent(model="nuextract:3.8b-q4_K_M", tavily_api_key=tavily_api_key)

class SearchRequest(BaseModel):
    """Model for search requests."""
    query: str

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE Web Search Agent is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/search")
async def search(request: SearchRequest):
    """
    Endpoint to perform a web search.
    
    Args:
        request: SearchRequest containing the query
        
    Returns:
        Search results
    """
    try:
        logger.info(f"Received search request: {request.query}")
        
        # Call the WebSearchAgent to perform the search
        result = await web_search_agent.search(request.query)
        
        return {"success": True, "query": request.query, "result": result}
    except Exception as e:
        logger.error(f"Error performing search: {e}")
        raise HTTPException(status_code=500, detail=f"Error performing search: {str(e)}")

@app.get("/utcp")
async def utcp_manual():
    """UTCP Manual endpoint for tool discovery."""
    # Create UTCP Manual with tools provided by this agent
    manual = UtcpManual(
        manual_version="1.0.0",
        utcp_version="1.0.2",
        tools=[
            Tool(
                name="search",
                description="Perform a web search using the Tavily API",
                tags=["web", "search"],
                inputs={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to perform"
                        }
                    },
                    "required": ["query"]
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the search was successful"
                        },
                        "query": {
                            "type": "string",
                            "description": "The search query performed"
                        },
                        "result": {
                            "type": "string",
                            "description": "The search results"
                        },
                        "error": {
                            "type": "string",
                            "description": "Error message if search failed"
                        }
                    }
                },
                tool_call_template=HttpCallTemplate(
                    name="web_search",
                    call_template_type="http",
                    url="http://localhost:8007/search",  # This would need to be configurable in production
                    http_method="POST"
                )
            )
        ]
    )
    return manual

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    pass

if __name__ == "__main__":
    uvicorn.run(
        "web_search_app:app",
        host="0.0.0.0",
        port=8007,
        reload=True,
        log_level="info"
    )