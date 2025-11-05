"""
Web Search Agent App for the External Context Engine (ECE) v2.0 (Async).

This module implements the FastAPI app for the Web Search agent using a fully
asynchronous model to align with the ECE architecture and enable non-blocking I/O.
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, List
import logging

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Import the WebSearchAgent (now using local implementation)
from ece.agents.tier2.web_search_agent import WebSearchAgent

# Import UTCP data models for manual creation
from utcp.data.utcp_manual import UtcpManual
from utcp.data.tool import Tool
from utcp_http.http_call_template import HttpCallTemplate

# Import and set up ECE logging system
try:
    from ece.common.logging_config import get_logger

    logger = get_logger("web_search")
except ImportError:
    # Fallback if logging config not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Could not import ECE logging system, using default logging")

# Initialize FastAPI app
app = FastAPI(
    title="ECE Web Search Agent",
    description="The WebSearchAgent provides local web search capabilities for the ECE.",
    version="1.0.0",
)

# Create an instance of the WebSearchAgent (now using local implementation)
web_search_agent = WebSearchAgent(
    model="nuextract:3.8b-q4_K_M", api_base="http://localhost:8085/v1"
)


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
async def search_post(request: Request):
    """
    POST endpoint to perform a web search using the local implementation.
    Handles both JSON body and form data.

    Args:
        request: Request object that may contain JSON body or form data

    Returns:
        Search results
    """
    try:
        # Try to get parameters from JSON body first
        try:
            body = await request.json()
            query = body.get("query")
        except:
            # If JSON parsing fails, try to get from form data
            try:
                form = await request.form()
                query = form.get("query")
            except:
                # If both fail, use query parameters
                query = request.query_params.get("query")

        if not query:
            raise HTTPException(status_code=400, detail="query is required")

        logger.info(f"Received POST search request: {query}")

        # Call the WebSearchAgent to perform the search (now using local implementation)
        result = await web_search_agent.search(query=query)

        # Extract websites from search results
        websites_searched = result.get("websites_searched", [])

        return {
            "success": True,
            "query": query,
            "result": result.get("answer", ""),
            "websites_searched": websites_searched,
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error performing search: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error performing search: {str(e)}"
        )


@app.get("/search")
async def search_get(query: str):
    """
    GET endpoint to perform a web search using the local implementation.

    Args:
        query: The search query to perform

    Returns:
        Search results
    """
    try:
        logger.info(f"Received GET search request: {query}")

        # Call the WebSearchAgent to perform the search (now using local implementation)
        result = await web_search_agent.search(query=query)

        # Extract websites from search results
        websites_searched = result.get("websites_searched", [])

        return {
            "success": True,
            "query": query,
            "result": result.get("answer", ""),
            "websites_searched": websites_searched,
        }
    except Exception as e:
        logger.error(f"Error performing search: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error performing search: {str(e)}"
        )


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
                description="Perform a local web search using DuckDuckGo and content scraping",
                tags=["web", "search", "local"],
                inputs={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to perform",
                        }
                    },
                    "required": ["query"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the search was successful",
                        },
                        "query": {
                            "type": "string",
                            "description": "The search query performed",
                        },
                        "result": {
                            "type": "string",
                            "description": "The search results",
                        },
                        "websites_searched": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of websites that were searched",
                        },
                        "error": {
                            "type": "string",
                            "description": "Error message if search failed",
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="web_search",
                    call_template_type="http",
                    url="http://localhost:8007/search",  # This would need to be configurable in production
                    http_method="POST",
                ),
            )
        ],
    )
    return manual


# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    pass


if __name__ == "__main__":
    uvicorn.run(
        "web_search_app:app", host="0.0.0.0", port=8007, reload=True, log_level="info"
    )
