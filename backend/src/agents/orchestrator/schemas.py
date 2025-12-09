from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class IntentType(str, Enum):
    QUERY = "QUERY"
    ACTION = "ACTION"
    CLARIFICATION = "CLARIFICATION"
    CHIT_CHAT = "CHIT_CHAT"

class NextAction(str, Enum):
    CALL_TOOL = "CALL_TOOL"
    FINALIZE_RESPONSE = "FINALIZE_RESPONSE"
    ASK_USER = "ASK_USER"

class SGRStep(BaseModel):
    step_id: int
    description: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    reasoning: str

class SGRPlan(BaseModel):
    analysis: str = Field(..., description="Analysis of the current situation and user request")
    intent: IntentType
    confidence_score: float
    steps: List[SGRStep]
    next_action: NextAction
    final_response: Optional[str] = Field(None, description="The final response to the user if next_action is FINALIZE_RESPONSE")
