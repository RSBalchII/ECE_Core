from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from src.bootstrap import get_components

router = APIRouter()


@router.get("/context/{session_id}")
async def get_context(request_obj: Request, session_id: str):
    components = get_components(request_obj.app)
    memory = components.get("memory")
    if not memory:
        raise HTTPException(status_code=503, detail="Not initialized")
    active = await memory.get_active_context(session_id)
    summaries = await memory.get_summaries(session_id)
    return {"session_id": session_id, "active_context": active, "active_tokens": memory.count_tokens(active) if active else 0, "summaries": summaries}


@router.delete("/context/{session_id}")
async def clear_context(request_obj: Request, session_id: str):
    """Clear the active context cache for a session (force reset)."""
    components = get_components(request_obj.app)
    memory = components.get("memory")
    if not memory:
        raise HTTPException(status_code=503, detail="Not initialized")
    
    await memory.clear_session_context(session_id)
    return {"status": "success", "message": "Context cache cleared", "session_id": session_id}


@router.get("/memories/{category}")
async def get_memories_by_category(request_obj: Request, category: str, limit: int = 10):
    components = get_components(request_obj.app)
    memory = components.get("memory")
    if not memory:
        raise HTTPException(status_code=503, detail="Not initialized")
    memories = await memory.get_recent_by_category(category, limit)
    return {"category": category, "count": len(memories), "memories": memories}


@router.get("/memories/search")
async def search_memories(request_obj: Request, query: str | None = None, category: str = None, tags: str = None, limit: int = 10):
    components = get_components(request_obj.app)
    memory = components.get("memory")
    if not memory:
        raise HTTPException(status_code=503, detail="Not initialized")
    tag_list = [t.strip() for t in tags.split(',')] if tags else None
    # If query provided, pass as a content search
    memories = await memory.search_memories(query_text=query, category=category, tags=tag_list, limit=limit)
    return {"query": {"query": query, "category": category, "tags": tag_list}, "count": len(memories), "memories": memories}


@router.get("/memories")
async def get_memories(request_obj: Request, limit: int = 10):
    """Compatibility endpoint: return recent memories (search with no filters)."""
    components = get_components(request_obj.app)
    memory = components.get("memory")
    if not memory:
        raise HTTPException(status_code=503, detail="Not initialized")
    memories = await memory.search_memories(limit=limit)
    return {"count": len(memories), "memories": memories}


class MemoryAddRequest(BaseModel):
    category: str
    content: str
    tags: list[str] | None = None
    importance: int = 5
    metadata: dict | None = None


@router.post("/memories")
async def add_memory(request_obj: Request, body: MemoryAddRequest):
    components = get_components(request_obj.app)
    memory = components.get("memory")
    if not memory:
        raise HTTPException(status_code=503, detail="Not initialized")
    # Ensure Neo4j is available (avoid accepting writes that won't be persisted)
    if not getattr(memory, 'neo4j', None) or not getattr(memory.neo4j, 'neo4j_driver', None):
        raise HTTPException(status_code=503, detail="Neo4j unavailable; cannot add memory")
    await memory.add_memory(session_id="api", content=body.content, category=body.category, tags=body.tags, importance=body.importance, metadata=body.metadata)
    return {"status": "success", "message": "Memory added"}
