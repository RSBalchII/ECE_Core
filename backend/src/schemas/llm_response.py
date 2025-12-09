from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional
from src.tool_call_models import ToolCall


class LLMStructuredResponse(BaseModel):
    """Validated LLM response expected by downstream flows.

    - `answer`: Main assistant text
    - `sources`: Optional list of source IDs or URLs
    - `tool_calls`: Optional list of tool calls that should be executed
    - `confidence`: Optional string describing confidence
    """

    answer: str = Field(..., description="Main text answer from the LLM")
    sources: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    confidence: Optional[str] = Field(None, description="Optional model self-reported confidence")
