"""
Browser Bridge Plugin for ECE

This plugin provides API endpoints for the Chrome extension to communicate with the ECE system.
It allows for chat ingestion and context retrieval from the browser.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
import logging
from src.config import settings
from src.security import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/browser", tags=["browser_bridge"])

# Pydantic models for request/response
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = None


class IngestRequest(BaseModel):
    messages: List[ChatMessage]
    source_url: str = None
    session_id: str = None


class IngestResponse(BaseModel):
    success: bool
    processed_count: int
    message: str


class ContextRequest(BaseModel):
    draft_prompt: str
    max_results: int = 10


class ContextResponse(BaseModel):
    success: bool
    context: str
    retrieved_count: int


# Dependencies
async def get_components():
    """Get ECE components from app state."""
    from src.bootstrap import get_components as get_ece_components
    # This will be injected by the main app
    return get_ece_components


@router.post("/ingest", response_model=IngestResponse)
async def ingest_browser_chat(
    request: IngestRequest,
    # components: dict = Depends(get_components),
    auth: bool = Depends(verify_api_key)  # Only if auth is required
):
    """
    Ingest chat messages from the browser extension.
    Saves messages to Neo4j using the Archivist agent.
    """
    try:
        # Import components from the main app state
        from src.app_factory import app
        components = {
            "memory": getattr(app.state, "memory", None),
            "archivist_agent": getattr(app.state, "archivist_agent", None),
            "context_mgr": getattr(app.state, "context_mgr", None),
        }
        
        # Validate components
        if not components["memory"]:
            raise HTTPException(status_code=500, detail="Memory system not available")
        
        # Process each message and save to memory
        processed_count = 0
        for msg in request.messages:
            try:
                # Add to memory system
                memory_id = await components["memory"].add_memory(
                    session_id=request.session_id or "browser_session",
                    content=f"[Browser Chat] {msg.role.title()}: {msg.content}",
                    category="browser_chat",
                    tags=["browser", "chat", msg.role.lower()],
                    importance=5,
                    metadata={
                        "source": "browser_extension",
                        "url": request.source_url,
                        "role": msg.role,
                        "timestamp": msg.timestamp
                    }
                )
                
                if memory_id:
                    processed_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to process message: {e}")
                continue
        
        logger.info(f"Processed {processed_count}/{len(request.messages)} browser chat messages")
        
        return IngestResponse(
            success=True,
            processed_count=processed_count,
            message=f"Successfully processed {processed_count} out of {len(request.messages)} messages"
        )
        
    except Exception as e:
        logger.error(f"Error ingesting browser chat: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest chat: {str(e)}")


@router.post("/context", response_model=ContextResponse)
async def get_context_for_prompt(
    request: ContextRequest,
    # components: dict = Depends(get_components),
    auth: bool = Depends(verify_api_key)  # Only if auth is required
):
    """
    Retrieve relevant context for a draft prompt from the browser.
    """
    try:
        # Import components from the main app state
        from src.app_factory import app
        components = {
            "memory": getattr(app.state, "memory", None),
            "context_mgr": getattr(app.state, "context_mgr", None),
        }
        
        # Validate components
        if not components["memory"]:
            raise HTTPException(status_code=500, detail="Memory system not available")
        
        # Search for relevant memories
        try:
            # Try to search with the draft prompt
            results = await components["memory"].search_memories(
                query_text=request.draft_prompt,
                limit=request.max_results
            )
        except Exception as search_error:
            logger.warning(f"Search failed: {search_error}")
            results = []
        
        # Format the context
        if results:
            context_parts = ["Relevant Memories:", "-" * 40]
            for i, result in enumerate(results, 1):
                content = result.get('content', '')[:200] + "..." if len(result.get('content', '')) > 200 else result.get('content', '')
                score = result.get('score', 0)
                context_parts.append(f"{i}. [{score:.2f}] {content}")
                context_parts.append("")
            
            formatted_context = "\n".join(context_parts)
        else:
            formatted_context = "No relevant memories found."
        
        logger.info(f"Retrieved {len(results)} context items for prompt: {request.draft_prompt[:50]}...")
        
        return ContextResponse(
            success=True,
            context=formatted_context,
            retrieved_count=len(results)
        )
        
    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve context: {str(e)}")


@router.get("/health")
async def browser_bridge_health():
    """Health check for the browser bridge."""
    return {
        "status": "healthy",
        "service": "Browser Bridge Plugin",
        "api_version": "1.0.0"
    }


# Additional utility endpoints
@router.get("/session/current")
async def get_current_session():
    """Get information about the current browser session."""
    return {
        "session_id": "browser_session",
        "connected": True,
        "features": ["chat_ingestion", "context_retrieval"]
    }