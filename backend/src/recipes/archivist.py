from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import time
import json
from datetime import datetime, timezone

from src.bootstrap import get_components
from src.security import verify_api_key
from src.models import PlaintextMemory, SourceType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["archivist"])

class ExtensionIngestRequest(BaseModel):
    content: str
    type: str
    adapter: Optional[str] = None

class IngestResponse(BaseModel):
    status: str
    memory_ids: List[str]
    message: str

@router.post("/ingest", response_model=IngestResponse)
async def ingest_content(
    request_obj: Request, 
    payload: ExtensionIngestRequest, 
    authenticated: bool = Depends(verify_api_key)
):
    """
    Archivist Endpoint: Ingests raw content, distills it, and commits it to long-term memory.
    This bypasses the standard chat flow to ensure high-quality, verified memories are stored.
    """
    components = get_components(request_obj.app)
    memory = components.get("memory")
    
    if not memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")

    try:
        logger.info(f"Archivist ingesting content from adapter: {payload.adapter}")
        
        # Map source type
        source_type = SourceType.WEB_PAGE
        if "gemini" in payload.type.lower() or (payload.adapter and "gemini" in payload.adapter.lower()):
            source_type = SourceType.GEMINI_CHAT
        
        # Create PlaintextMemory (Directive INJ-A1)
        plaintext_memory = PlaintextMemory(
            source_type=source_type,
            source_identifier=f"browser_session_{datetime.now().strftime('%Y%m%d')}",
            content=payload.content,
            metadata={
                "adapter": payload.adapter,
                "raw_type": payload.type,
                "ingested_by": "Archivist"
            }
        )
        
        # Persist to Corpus (ark_corpus.jsonl)
        # Using standard open for simplicity and robustness
        with open("ark_corpus.jsonl", "a", encoding="utf-8") as f:
            f.write(plaintext_memory.json() + "\n")
            
        # Index via MemoryManager (Reflex Memory)
        session_id = f"archivist-{int(time.time())}"
        
        # Use memory.add_memory to trigger the full pipeline (Distillation -> Neo4j -> Vector)
        memory_id = await memory.add_memory(
            session_id=session_id,
            content=plaintext_memory.content,
            category="knowledge",
            tags=["#ingested", f"#{source_type.value.lower()}"],
            importance=3,
            metadata=plaintext_memory.metadata
        )

        return IngestResponse(
            status="success",
            memory_ids=[memory_id] if memory_id else [],
            message="Content successfully ingested, archived, and indexed."
        )

    except Exception as e:
        logger.exception("Archivist ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))
