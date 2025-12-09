#!/usr/bin/env python3
"""
Modular ECE Core + MCP Server Launcher

This launcher provides a unified server with optional MCP integration.
MCP endpoints can be enabled/disabled via configuration in config.yaml.
"""
from __future__ import annotations

import logging
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional

from src.config import settings
from src.bootstrap import create_app, get_components
from src.security import verify_api_key


def create_modular_app() -> FastAPI:
    """
    Create a modular ECE application with optional MCP integration.
    MCP endpoints are included based on configuration.
    """
    # Create the main ECE application
    ece_app = create_app()

    # Add MCP endpoints if enabled in configuration
    if getattr(settings, 'mcp_enabled', False):
        _add_mcp_endpoints(ece_app)

    # Add modular health check
    @ece_app.get("/health/modular")
    async def modular_health():
        has_mcp = getattr(settings, 'mcp_enabled', False)
        return {
            "status": "ok",
            "service": "ECE Modular Server",
            "mcp_enabled": has_mcp,
            "main_api": True
        }

    return ece_app


def _add_mcp_endpoints(app: FastAPI):
    """Add MCP endpoints to the main application."""
    from fastapi import FastAPI

    # Create MCP sub-app to keep routes organized
    mcp_app = FastAPI(title="ECE MCP Server (Integrated)", include_in_schema=False)

    # MCP Tool Schema
    class ToolSchema(BaseModel):
        name: str
        description: str
        inputSchema: Dict[str, Any]

    class ToolCall(BaseModel):
        name: str
        arguments: Dict[str, Any]

    # Define MCP tools
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

    # Tool aliases
    TOOL_ALIASES = {
        "write_memory": ADD_MEMORY_TOOL.name,
        "read_memory": SEARCH_MEMORIES_TOOL.name,
        "get_memory_summaries": GET_RECENT_SUMMARIES_TOOL.name,
    }

    # MCP routes with authentication
    @mcp_app.get("/tools")
    async def list_mcp_tools(request: Request):
        if settings.ece_require_auth:
            await verify_api_key()

        canonical = [ADD_MEMORY_TOOL.dict(), SEARCH_MEMORIES_TOOL.dict(), GET_RECENT_SUMMARIES_TOOL.dict()]
        aliases = []

        for alias_name, canonical_name in TOOL_ALIASES.items():
            for c in canonical:
                if c["name"] == canonical_name:
                    schema = c.copy()
                    schema["name"] = alias_name
                    schema["description"] = f"Alias for {canonical_name}"
                    aliases.append(schema)
                    break
        return {"tools": canonical + aliases}

    @mcp_app.post("/call")
    async def call_mcp_tool(tool_call: ToolCall, request: Request):
        if settings.ece_require_auth:
            await verify_api_key()

        components = get_components(app)
        memory = components.get("memory")

        if not memory or not memory.neo4j:
            raise HTTPException(status_code=503, detail="Neo4j store not initialized")

        try:
            # Resolve aliases to canonical tool name
            name = TOOL_ALIASES.get(tool_call.name, tool_call.name)
            p = tool_call.arguments

            if name == ADD_MEMORY_TOOL.name:
                result = await memory.neo4j.add_memory(
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
                result = await memory.neo4j.search_memories(
                    p.get("query", ""),
                    p.get("category"),
                    int(p.get("limit", 10))
                )
                return {"tool": tool_call.name, "status": "success", "result": result}

            elif name == GET_RECENT_SUMMARIES_TOOL.name:
                result = await memory.neo4j.get_summaries(
                    str(p.get("session_id")),
                    int(p.get("limit", 5))
                )
                return {"tool": tool_call.name, "status": "success", "result": result}

            else:
                raise HTTPException(status_code=404, detail=f"Tool not found: {tool_call.name}")

        except HTTPException:
            raise
        except Exception as e:
            logging.exception("MCP call failed")
            return {"tool": tool_call.name, "status": "error", "error": str(e)}

    @mcp_app.get("/sse")
    async def sse_status(request: Request):
        if settings.ece_require_auth:
            await verify_api_key()

        try:
            from sse_starlette.sse import EventSourceResponse
        except Exception:
            raise HTTPException(status_code=501, detail="SSE streaming not supported (missing sse_starlette dependency)")

        async def generator():
            import asyncio
            i = 0
            while True:
                if await request.is_disconnected():
                    break
                yield {"event": "status", "data": f"ok-{i}"}
                i += 1
                await asyncio.sleep(3)

        return EventSourceResponse(generator())

    # Mount MCP endpoints under the main ECE app
    app.mount("/mcp", mcp_app)

    # Add MCP-specific health check
    @app.get("/health/mcp")
    async def mcp_health():
        components = get_components(app)
        memory = components.get("memory")
        active = bool(memory and memory.neo4j and memory.neo4j.neo4j_driver is not None)
        return {
            "status": "ok",
            "service": "ECE MCP Integration",
            "active": active,
            "enabled": getattr(settings, 'mcp_enabled', False)
        }


if __name__ == '__main__':
    import uvicorn
    logging.basicConfig(
        level=getattr(logging, settings.ece_log_level),
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    app = create_modular_app()

    print(f"🚀 Starting ECE Core (Modular) on {settings.ece_host}:{settings.ece_port}")
    print(f"   - Main API: http://{settings.ece_host}:{settings.ece_port}")
    print(f"   - MCP Enabled: {getattr(settings, 'mcp_enabled', False)}")

    if getattr(settings, 'mcp_enabled', False):
        print(f"   - MCP Tools: http://{settings.ece_host}:{settings.ece_port}/mcp/tools")
        print(f"   - MCP Call: http://{settings.ece_host}:{settings.ece_port}/mcp/call")
        print(f"   - MCP Health: http://{settings.ece_host}:{settings.ece_port}/health/mcp")

    print(f"   - Health: http://{settings.ece_host}:{settings.ece_port}/health")
    print(f"   - Modular Health: http://{settings.ece_host}:{settings.ece_port}/health/modular")

    uvicorn.run(
        app,
        host=settings.ece_host,
        port=settings.ece_port,
        log_level=settings.ece_log_level.lower()
    )