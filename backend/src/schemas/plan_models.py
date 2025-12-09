from __future__ import annotations

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to invoke, or 'none' for no tool")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    reasoning: Optional[str] = Field(None, description="Optional human-friendly reasoning for step")


class PlanResult(BaseModel):
    goal: str = Field(..., description="High-level goal for the plan")
    steps: List[PlanStep] = Field(default_factory=list, description="Ordered steps to accomplish the goal")


__all__ = ["PlanResult", "PlanStep"]
