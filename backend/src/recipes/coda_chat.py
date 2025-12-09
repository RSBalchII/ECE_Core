from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any, List, Dict, AsyncGenerator
import httpx
import json, time, asyncio, logging

from src.bootstrap import get_components
from src.security import verify_api_key
from src.prompts import build_system_prompt
from src.tools import ToolExecutor
from src.config import settings
from src.agents.orchestrator.orchestrator import SGROrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["coda_chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str
    system_prompt: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    context_tokens: int


@router.post("/", response_model=ChatResponse)
async def chat(request_obj: Request, payload: ChatRequest, authenticated: bool = Depends(verify_api_key)):
    """
    SGR-enabled chat endpoint.
    Uses the SGROrchestrator to Think -> Plan -> Act.
    """
    components = get_components(request_obj.app)
    memory = components.get("memory")
    llm = components.get("llm")
    context_mgr = components.get("context_mgr")
    chunker = components.get("chunker")
    plugin_manager = components.get("plugin_manager")
    mcp_client = components.get("mcp_client")
    audit_logger = components.get("audit_logger")

    if not all([memory, llm, context_mgr, chunker]):
        raise HTTPException(status_code=503, detail="Not initialized")

    try:
        # Mark session as active
        try:
            await memory.touch_session(payload.session_id)
        except Exception:
            pass

        # 1. Build Context
        processed_message = await chunker.process_large_input(payload.message, query_context="User is chatting with their memory-augmented AI")
        full_context = await context_mgr.build_context(payload.session_id, processed_message)

        # 2. Initialize Tool Executor
        tool_executor = ToolExecutor(plugin_manager=plugin_manager, mcp_client=mcp_client)

        # 3. Initialize SGR Orchestrator
        orchestrator = SGROrchestrator(
            llm_client=llm,
            tool_executor=tool_executor,
            audit_logger=audit_logger
        )

        # 4. Run the Loop
        final_response = await orchestrator.run_loop(
            session_id=payload.session_id,
            user_message=processed_message,
            context=full_context
        )

        # 5. Save to Memory
        await memory.save_active_context(payload.session_id, f"{full_context}\n\nAssistant: {final_response}")
        
        # 6. Log Audit
        if audit_logger:
            await audit_logger.log_event(
                session_id=payload.session_id,
                event_type="chat_turn",
                content=final_response,
                metadata={"model": "SGR_Orchestrator"}
            )

        return ChatResponse(
            response=final_response,
            session_id=payload.session_id,
            context_tokens=len(full_context) // 4 # Approx
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Note: Streaming endpoint would need similar refactoring to stream the SGR steps
