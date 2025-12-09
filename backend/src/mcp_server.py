#!/usr/bin/env python3
"""
Minimal MCP server for ECE memory graph
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.memory.neo4j_store import Neo4jStore
from src.config import settings
from fastapi import Request

logger = logging.getLogger(__name__)
app = FastAPI(title="ECE MCP Server")


class ToolSchema(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]


class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]


ADD_MEMORY_TOOL = ToolSchema(
    name="add_memory",
    description="Add a memory node into ECE's Neo4j store",
    inputSchema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "content": {"type": "string"},
            "category": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "importance": {"type": "number"},
            "metadata": {"type": "object"},
            "entities": {"type": "array", "items": {"type": "object"}}
        },
        "required": ["session_id", "content", "category"]
    },
)

SEARCH_MEMORIES_TOOL = ToolSchema(
    name="search_memories",
    description="Search memories using the Neo4j store",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "category": {"type": "string"},
            "limit": {"type": "number"}
        },
        "required": ["query"]
    },
)

GET_RECENT_SUMMARIES_TOOL = ToolSchema(
    name="get_summaries",
    description="Get recent session summaries",
    inputSchema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "limit": {"type": "number"}
        },
        "required": ["session_id"]
    },
)


_neo4j_store: Optional[Neo4jStore] = None

# Alias map for user-facing tools (Cline / other clients often use 'read_memory'/'write_memory')
TOOL_ALIASES = {
    "write_memory": ADD_MEMORY_TOOL.name,
    "read_memory": SEARCH_MEMORIES_TOOL.name,
    "get_memory_summaries": GET_RECENT_SUMMARIES_TOOL.name,
}


@app.on_event("startup")
async def _startup_event() -> None:
    global _neo4j_store
    _neo4j_store = Neo4jStore()
    try:
        await _neo4j_store.initialize()
    except Exception as e:
        logger.warning(f"Failed to initialize Neo4jStore: {e}")


@app.on_event("shutdown")
async def _shutdown_event() -> None:
    global _neo4j_store
    if _neo4j_store:
        await _neo4j_store.close()


@app.get("/mcp/tools")
async def list_tools(request: Request):
    # Enforce bearer token if required
    if settings.ece_require_auth:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing authorization token")
        token = auth.split(None, 1)[1].strip()
        configured = settings.mcp_api_key or settings.ece_api_key
        if not configured or token != configured:
            raise HTTPException(status_code=403, detail="Forbidden: invalid API key")
    # Expose canonical tools and also alias tools so clients using common names can discover them
    canonical = [ADD_MEMORY_TOOL.dict(), SEARCH_MEMORIES_TOOL.dict(), GET_RECENT_SUMMARIES_TOOL.dict()]
    aliases = []
    # Build alias schemas by copying canonical body but forcing name/description
    for alias_name, canonical_name in TOOL_ALIASES.items():
        for c in canonical:
            if c["name"] == canonical_name:
                schema = c.copy()
                schema["name"] = alias_name
                schema["description"] = f"Alias for {canonical_name}"
                aliases.append(schema)
                break
    return {"tools": canonical + aliases}


@app.post("/mcp/call")
async def call_tool(tool_call: ToolCall, request: Request):
    global _neo4j_store
    if not _neo4j_store:
        raise HTTPException(status_code=503, detail="Neo4j store not initialized")
    # Enforce bearer token if required
    if settings.ece_require_auth:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing authorization token")
        token = auth.split(None, 1)[1].strip()
        configured = settings.mcp_api_key or settings.ece_api_key
        if not configured or token != configured:
            raise HTTPException(status_code=403, detail="Forbidden: invalid API key")

    try:
        # Resolve aliases to canonical tool name
        name = TOOL_ALIASES.get(tool_call.name, tool_call.name)
        if name == ADD_MEMORY_TOOL.name:
            p = tool_call.arguments
            result = await _neo4j_store.add_memory(
                session_id=p.get("session_id"),
                content=p.get("content"),
                category=p.get("category"),
                tags=p.get("tags", []),
                importance=int(p.get("importance", 5)),
                metadata=p.get("metadata") or {},
                entities=p.get("entities") or [],
            )
            return {"tool": tool_call.name, "status": "success", "result": {"id": result}}

        elif name == SEARCH_MEMORIES_TOOL.name:
            p = tool_call.arguments
            result = await _neo4j_store.search_memories(p.get("query", ""), p.get("category"), int(p.get("limit", 10)))
            return {"tool": tool_call.name, "status": "success", "result": result}

        elif name == GET_RECENT_SUMMARIES_TOOL.name:
            p = tool_call.arguments
            result = await _neo4j_store.get_summaries(str(p.get("session_id")), int(p.get("limit", 5)))
            return {"tool": tool_call.name, "status": "success", "result": result}

        else:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_call.name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("MCP call failed")
        return {"tool": tool_call.name, "status": "error", "error": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ECE MCP Server", "active": bool(_neo4j_store and _neo4j_store.neo4j_driver is not None)}


@app.get("/mcp/sse")
async def sse_status(request: Request):
    # Optional SSE endpoint for streaming / agent clients
    if settings.ece_require_auth:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing authorization token")
        token = auth.split(None, 1)[1].strip()
        configured = settings.mcp_api_key or settings.ece_api_key
        if not configured or token != configured:
            raise HTTPException(status_code=403, detail="Forbidden: invalid API key")
    try:
        from sse_starlette.sse import EventSourceResponse
    except Exception:
        raise HTTPException(status_code=501, detail="SSE streaming not supported (missing sse_starlette dependency)")

    async def generator():
        # Send an initial status
        i = 0
        while True:
            if await request.is_disconnected():
                break
            yield {"event": "status", "data": f"ok-{i}"}
            i += 1
            await asyncio.sleep(3)

    return EventSourceResponse(generator())


if __name__ == "__main__":
    # When run directly, start the MCP server using the configured host & port
    import uvicorn
    if not settings.mcp_enabled:
        print("MCP server is disabled in configuration. Set MCP_ENABLED to true to start the MCP server.")
    else:
        print(f"Starting MCP server on {settings.mcp_host}:{settings.mcp_port} (derived from settings)")
        uvicorn.run("src.mcp_server:app", host=settings.mcp_host, port=int(settings.mcp_port), log_level=settings.ece_log_level.lower())
