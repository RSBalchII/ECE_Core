from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class NextAction(str, Enum):
    CALL_TOOL = "CALL_TOOL"
    FINALIZE_RESPONSE = "FINALIZE_RESPONSE"
    ASK_USER = "ASK_USER"
    CHIT_CHAT = "CHIT_CHAT"

class IntentType(str, Enum):
    QUERY = "QUERY"
    ACTION = "ACTION"
    CLARIFICATION = "CLARIFICATION"
    CHIT_CHAT = "CHIT_CHAT"
    FINALIZE_RESPONSE = "FINALIZE_RESPONSE" # Added for local model compatibility

class ToolCall(BaseModel):
    name: str = Field(..., description="The name of the tool to call")
    arguments: Dict[str, Any] = Field(..., description="The arguments to pass to the tool")

class SGRPlan(BaseModel):
    context_analysis: str = Field(..., description="Analysis of the current situation, user request, and retrieved context.")
    intent: IntentType = Field(..., description="Classification of the user's intent.")
    confidence_score: float = Field(..., description="Confidence score between 0.0 and 1.0.")
    reasoning_trace: str = Field(..., description="Step-by-step logic explaining the decision.")
    next_action: NextAction = Field(..., description="The next action to take.")
    tool_call: Optional[ToolCall] = Field(None, description="The tool to call if next_action is CALL_TOOL.")
    final_response: Optional[str] = Field(None, description="The final response to the user if next_action is FINALIZE_RESPONSE or ASK_USER.")

