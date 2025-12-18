from fastapi import APIRouter, Depends, HTTPException, Request, Response
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
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    session_id: str
    context_tokens: int


@router.post("/", response_model=None)
async def chat(request_obj: Request, payload: ChatRequest):
    """
    SGR-enabled chat endpoint.
    Uses the SGROrchestrator to Think -> Plan -> Act.
    """
    logger.info(f"Received chat request for session: {payload.session_id} with message: {payload.message[:50]}...")
    try:
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

            # Define Native Tools
            async def store_memory(content: str, category: str = "general", tags: List[str] = None):
                """Store a new memory in the long-term storage."""
                return await memory.add_memory(session_id=payload.session_id, content=content, category=category, tags=tags)

            async def retrieve_memory(query: str, limit: int = 5):
                """Retrieve relevant memories based on a query."""
                # Enforce strict limit to prevent context overflow in browser
                limit = min(limit, 5)
                logger.info(f"Executing retrieve_memory with query: {query} (limit capped to {limit})")
                results = await memory.search_memories(query_text=query, limit=limit)
                logger.info(f"retrieve_memory returned {len(results)} results")
                # Sanitize and truncate results to prevent browser crashes
                sanitized_results = []
                for res in results:
                    # Create a safe copy with only essential fields
                    safe_res = {
                        "content": str(res.get("content", ""))[:1000], # Truncate content
                        "category": str(res.get("category", "")),
                        "created_at": str(res.get("created_at", "")),
                        "score": res.get("score")
                    }
                    sanitized_results.append(safe_res)
                return sanitized_results

            native_tools = [
                {
                    "name": "store_memory",
                    "description": "Store a new memory in the long-term storage. Use this when the user asks you to remember something.",
                    "func": store_memory,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "The content to remember"},
                            "category": {"type": "string", "description": "Category (e.g., 'project', 'personal', 'fact')"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"}
                        },
                        "required": ["content"]
                    }
                },
                {
                    "name": "retrieve_memory",
                    "description": "Retrieve relevant memories based on a query. Use this to recall facts or past conversations.",
                    "func": retrieve_memory,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The search query"},
                            "limit": {"type": "integer", "description": "Max number of results (default 5)"}
                        },
                        "required": ["query"]
                    }
                }
            ]

            # 2. Initialize Tool Executor
            tool_executor = ToolExecutor(
                plugin_manager=plugin_manager, 
                mcp_client=mcp_client,
                tool_parser=None,
                tool_validator=None,
                llm_client=None,
                audit_logger=audit_logger,
                native_tools=native_tools
            )

            # 3. Initialize SGR Orchestrator
            orchestrator = SGROrchestrator(
                llm_client=llm,
                tool_executor=tool_executor,
                audit_logger=audit_logger
            )

            if payload.stream:
                async def event_generator():
                    queue = asyncio.Queue()
                    
                    async def stream_handler(chunk):
                        await queue.put({"type": "token", "content": chunk})
                        
                    task = asyncio.create_task(orchestrator.run_loop(
                        session_id=payload.session_id,
                        user_message=processed_message,
                        context=full_context,
                        stream_handler=stream_handler
                    ))
                    
                    final_response = ""
                    
                    while not task.done():
                        try:
                            get_queue = asyncio.create_task(queue.get())
                            done, pending = await asyncio.wait([get_queue, task], return_when=asyncio.FIRST_COMPLETED)
                            
                            if get_queue in done:
                                item = get_queue.result()
                                yield f"data: {json.dumps(item)}\n\n"
                            else:
                                get_queue.cancel()
                                break
                        except Exception:
                            break
                            
                    while not queue.empty():
                        item = await queue.get()
                        yield f"data: {json.dumps(item)}\n\n"
                        
                    if task.exception():
                        yield f"data: {json.dumps({'error': str(task.exception())})}\n\n"
                        return
                    
                    final_response = task.result()
                    
                    # Save to Memory (Background)
                    try:
                        await memory.save_active_context(payload.session_id, f"{full_context}\n\nAssistant: {final_response}")
                        await memory.add_memory(
                            session_id=payload.session_id,
                            content=payload.message,
                            category="conversation",
                            tags=["user", "chat"],
                            importance=1
                        )
                        await memory.add_memory(
                            session_id=payload.session_id,
                            content=final_response,
                            category="conversation",
                            tags=["assistant", "chat"],
                            importance=1
                        )
                    except Exception as e:
                        logger.error(f"Failed to persist chat to Neo4j: {e}")
                        
                    yield "data: [DONE]\n\n"

                return StreamingResponse(event_generator(), media_type="text/event-stream")

            # 4. Run the Loop (Non-streaming)
            final_response = await orchestrator.run_loop(
                session_id=payload.session_id,
                user_message=processed_message,
                context=full_context
            )

            # 5. Save to Memory
            # Build full context entry including both user and assistant turns
            new_context_entry = f"User: {payload.message}\nAssistant: {final_response}"
            full_context_to_save = f"{full_context}\n\n{new_context_entry}"

            # Save to Hot Cache (Redis) - Force save even if response contains errors
            await memory.save_active_context(payload.session_id, full_context_to_save)
            logger.info(f"Saved active context for session {payload.session_id} (Length: {len(full_context_to_save)} chars)")
            
            # Save to Permanent Graph (Neo4j)
            try:
                # User Message
                await memory.add_memory(
                    session_id=payload.session_id,
                    content=payload.message,
                    category="conversation",
                    tags=["user", "chat"],
                    importance=1
                )
                # Assistant Message
                await memory.add_memory(
                    session_id=payload.session_id,
                    content=final_response,
                    category="conversation",
                    tags=["assistant", "chat"],
                    importance=1
                )
            except Exception as e:
                logger.error(f"Failed to persist chat to Neo4j: {e}")
            
            # 6. Log Audit
            if audit_logger:
                await audit_logger.log_event(
                    session_id=payload.session_id,
                    event_type="chat_turn",
                    content=final_response,
                    metadata={"model": "SGR_Orchestrator"}
                )

            response_data = ChatResponse(
                response=final_response,
                session_id=payload.session_id,
                context_tokens=len(full_context) // 4 # Approx
            )
            
            # Force UTF-8 encoding
            return Response(
                content=response_data.model_dump_json(),
                media_type="application/json; charset=utf-8"
            )
        except Exception as e:
            logger.exception("Error in chat endpoint")
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Critical error in chat endpoint wrapper")
        raise HTTPException(status_code=500, detail=str(e))

# Note: Streaming endpoint would need similar refactoring to stream the SGR steps
