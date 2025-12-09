from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class SourceType(str, Enum):
    GEMINI_CHAT = "GEMINI_CHAT"
    WEB_PAGE = "WEB_PAGE"
    USER_NOTE = "USER_NOTE"
    PDF_DOCUMENT = "PDF_DOCUMENT"

class PlaintextMemory(BaseModel):
    """
    Directive INJ-A1: The foundational atom of the GraphR1 memory system.
    Represents a raw, immutable ingestion event (The 'Page' in GAM).
    """
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_type: SourceType
    source_identifier: str = Field(..., description="Filename, URL, or Session ID")
    ingest_timestamp_utc: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    original_timestamp_utc: Optional[str] = None
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0"

    class Config:
        schema_extra = {
            "example": {
                "uuid": "550e8400-e29b-41d4-a716-446655440000",
                "source_type": "GEMINI_CHAT",
                "source_identifier": "session_12345",
                "ingest_timestamp_utc": "2025-12-06T12:00:00Z",
                "content": "User: Hello\nGemini: Hi there!",
                "metadata": {
                    "author": "Gemini 3",
                    "word_count": 50,
                    "summary": "Greeting exchange"
                }
            }
        }
