"""Application bootstrap: provide create_app() with lifecycle initialization.

This module centralizes the app startup and shutdown lifecycle so `main.py`
becomes a thin routing module while the heavy initialization logic lives
here. The components are stored in `app.state` to be accessible from routes.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Any
from src.config import settings
from src.security import audit_logger
from src.memory import TieredMemory
from src.context import ContextManager
from src.intelligent_chunker import IntelligentChunker
from src.distiller import Distiller
from src.graph import GraphReasoner, MarkovianReasoner
from src.agents import VerifierAgent, ArchivistAgent
from src.agents.planner import PlannerAgent
try:
    from plugins.manager import PluginManager
except Exception:
    PluginManager = None
from src.tool_call_models import ToolCallParser, ToolCallValidator
from src.tools import ToolExecutor

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create FastAPI app with initialized components stored in app.state."""
    app = FastAPI(title="ECE_Core", version=settings.ece_version)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting ECE_Core with Markovian reasoning... (bootstrap)")
        memory = TieredMemory()
        await memory.initialize()

        mem_status = []
        if memory.redis and memory.redis.redis:
            mem_status.append("Redis")
        if memory.neo4j and memory.neo4j.neo4j_driver:
            mem_status.append("Neo4j")
        mem_str = " + ".join(mem_status) if mem_status else "No backends connected!"
        logger.info(f"Memory initialized ({mem_str})")

        # Import LLMClient here so unit tests can patch `src.llm.LLMClient` before booting the app
        from src.llm import LLMClient
        llm = LLMClient()
        logger.info("LLM client ready")
        context_mgr = ContextManager(memory, llm)
        logger.info("Context manager ready")
        chunker = IntelligentChunker(llm)
        logger.info("Intelligent chunker ready")
        distiller = Distiller(llm)
        logger.info("Distiller ready")
        graph_reasoner = GraphReasoner(memory, llm)
        logger.info("Graph reasoner ready (memory retrieval)")
        markov_reasoner = MarkovianReasoner(llm)
        logger.info("Markovian reasoner ready (chunked processing)")
        verifier_agent = VerifierAgent(memory, llm)
        logger.info("Verifier agent ready (Empirical Distrust)")
        archivist_agent = ArchivistAgent(memory, verifier_agent)
        # Start archivist background loop
        await archivist_agent.start()
        logger.info("Archivist agent ready (Maintenance Loop)")

        tool_parser = ToolCallParser()
        logger.info("Tool call parser ready (Pydantic validation)")
        tool_validator = None
        mcp_client = None
        plugin_manager = None

        # Initialize plugin manager (preferred) or MCP client for tools
        if PluginManager:
            plugin_manager = PluginManager(settings.__dict__)
            discovered = plugin_manager.discover()
            if discovered:
                logger.info(f"Plugin manager loaded plugins: {', '.join(discovered)}")
                tools = plugin_manager.list_tools()
                if tools:
                    tools_dict = {tool['name']: tool for tool in tools}
                    tool_validator = ToolCallValidator(tools_dict)
                    logger.info("Tool validator ready (via plugins)")
            else:
                logger.warning("Plugin manager enabled but no plugins discovered (tools disabled)")
        else:
            logger.warning("PluginManager not available (tools disabled)")

        # Initialize MCP client if configured
        if settings.mcp_enabled:
            try:
                from src.mcp_client import MCPClient as _MCPClient
                mcp_client = _MCPClient()
                logger.info("MCP client initialized for %s", mcp_client.base_url)
            except Exception as e:
                logger.warning("MCP client could not be initialized: %s", e)

        # Store components in app.state
        app.state.memory = memory
        app.state.llm = llm
        app.state.context_mgr = context_mgr
        app.state.chunker = chunker
        app.state.distiller = distiller
        app.state.graph_reasoner = graph_reasoner
        app.state.markov_reasoner = markov_reasoner
        app.state.verifier_agent = verifier_agent
        app.state.archivist_agent = archivist_agent
        app.state.plugin_manager = plugin_manager
        app.state.audit_logger = audit_logger
        app.state.tool_parser = tool_parser
        app.state.tool_validator = tool_validator
        # Planner agent
        planner_agent = PlannerAgent(llm)
        app.state.planner = planner_agent

        logger.info(f"ECE_Core running at http://{settings.ece_host}:{settings.ece_port}")
        try:
            yield
        finally:
            logger.info("Shutting down (bootstrap)...")
            try:
                await archivist_agent.stop()
            except Exception:
                pass
            try:
                await memory.close()
            except Exception:
                pass
            try:
                await llm.close()
            except Exception:
                pass

    app = FastAPI(title="ECE_Core", version=settings.ece_version, lifespan=lifespan)

    # DEBUG: Log all requests
    @app.middleware("http")
    async def log_requests(request, call_next):
        logger.info(f"Incoming request: {request.method} {request.url}")
        logger.info(f"Headers: {request.headers}")
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response

    # Configure CORS - Permissive for Debugging
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex='.*',  # Allow ANY origin matching this regex
        allow_credentials=True,   # Allow cookies/auth headers
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


def get_components(app: FastAPI) -> dict:
    """Return a dict of initialized components for convenience in routes.
    """
    return {
        "memory": getattr(app.state, "memory", None),
        "llm": getattr(app.state, "llm", None),
        "context_mgr": getattr(app.state, "context_mgr", None),
        "chunker": getattr(app.state, "chunker", None),
        "distiller": getattr(app.state, "distiller", None),
        "graph_reasoner": getattr(app.state, "graph_reasoner", None),
        "markov_reasoner": getattr(app.state, "markov_reasoner", None),
        "verifier_agent": getattr(app.state, "verifier_agent", None),
        "archivist_agent": getattr(app.state, "archivist_agent", None),
        "plugin_manager": getattr(app.state, "plugin_manager", None),
        "tool_parser": getattr(app.state, "tool_parser", None),
        "tool_validator": getattr(app.state, "tool_validator", None),
        "audit_logger": getattr(app.state, "audit_logger", None),
    }
