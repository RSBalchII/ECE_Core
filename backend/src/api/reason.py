from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any, List, Dict
from src.bootstrap import get_components

router = APIRouter()


class ReasonRequest(BaseModel):
    session_id: str
    question: str
    mode: str = "graph"


class ReasonResponse(BaseModel):
    answer: str
    reasoning_trace: List[Dict[str, Any]]
    iterations: int
    confidence: str


@router.post("/reason", response_model=ReasonResponse)
async def reason_with_graph(request_obj: Request, body: ReasonRequest):
    components = get_components(request_obj.app)
    memory = components.get("memory")
    llm = components.get("llm")
    graph_reasoner = components.get("graph_reasoner")
    markov_reasoner = components.get("markov_reasoner")
    context_mgr = components.get("context_mgr")
    if not all([memory, llm, graph_reasoner, markov_reasoner]):
        raise HTTPException(status_code=503, detail="Not initialized")
    try:
        if body.mode == "graph":
            result = await graph_reasoner.reason(body.session_id, body.question)
        elif body.mode == "markov":
            initial_context = await context_mgr.build_context(body.session_id, body.question)
            answer = await markov_reasoner.reason(body.question, initial_context)
            result = {
                "answer": answer,
                "reasoning_trace": [{"type": "markovian", "result": "Used Markovian chunked reasoning"}],
                "iterations": markov_reasoner.max_chunks,
                "confidence": "medium"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {body.mode}")

        await context_mgr.update_context(body.session_id, body.question, result["answer"])
        return ReasonResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reasoning/trace/{session_id}")
async def get_reasoning_trace(request_obj: Request, session_id: str):
    components = get_components(request_obj.app)
    memory = components.get("memory")
    if not memory:
        raise HTTPException(status_code=503, detail="Not initialized")
    summaries = await memory.get_summaries(session_id, limit=5)
    return {"session_id": session_id, "traces": summaries}
