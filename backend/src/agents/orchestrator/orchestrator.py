import json
import logging
from typing import List, Dict, Any, Optional
from src.llm import LLMClient
from src.tools import ToolExecutor
from src.agents.orchestrator.schemas import SGRPlan, NextAction, IntentType

logger = logging.getLogger(__name__)

SGR_SYSTEM_PROMPT = """
You are the Orchestrator for the Context Engine. Your goal is to "Think, Plan, then Act".
You must analyze the user's request and the current context, then produce a structured JSON plan.

You must output valid JSON matching this schema:
{
  "analysis": "Detailed analysis of the user's request and current state.",
  "intent": "QUERY" | "ACTION" | "CLARIFICATION" | "CHIT_CHAT",
  "confidence_score": 0.0 to 1.0,
  "steps": [
    {
      "step_id": 1,
      "description": "What this step does",
      "tool_name": "optional_tool_name_if_needed",
      "tool_args": { "arg1": "value" },
      "reasoning": "Why this tool is needed"
    }
  ],
  "next_action": "CALL_TOOL" | "FINALIZE_RESPONSE" | "ASK_USER",
  "final_response": "The final text response to the user (only if next_action is FINALIZE_RESPONSE or ASK_USER)"
}

RULES:
1. If you need to use a tool, set "next_action" to "CALL_TOOL" and define the tool in the first step.
2. Only plan ONE tool call at a time. You will get the result back in the next turn.
3. If you have enough information or no tools are needed, set "next_action" to "FINALIZE_RESPONSE".
4. If the user's request is unclear, set "next_action" to "ASK_USER".
5. Do not hallucinate tool names. Only use available tools.
"""

class SGROrchestrator:
    def __init__(self, llm_client: LLMClient, tool_executor: ToolExecutor, audit_logger=None):
        self.llm = llm_client
        self.tools = tool_executor
        self.audit = audit_logger
        self.max_turns = 5

    async def run_loop(self, session_id: str, user_message: str, context: str) -> str:
        """
        Executes the Schema-Guided Reasoning loop.
        """
        # Initialize conversation history for this run
        # We start with the retrieved context + user message
        # Note: 'context' here is the assembled context string from ContextManager
        
        current_history = [
            {"role": "system", "content": SGR_SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nUser Request: {user_message}"}
        ]

        for turn in range(self.max_turns):
            logger.info(f"SGR Turn {turn + 1}/{self.max_turns} for session {session_id}")
            
            # 1. Generate Plan
            try:
                # Force JSON mode if possible, or rely on prompt
                response_text = await self.llm.generate_response(
                    messages=current_history,
                    temperature=0.2, # Low temp for deterministic planning
                    json_mode=True
                )
                
                # Parse JSON
                try:
                    plan_data = json.loads(response_text)
                    plan = SGRPlan(**plan_data)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Failed to parse SGR plan: {e}. Response: {response_text}")
                    # Fallback: try to repair or just return the raw text if it looks like a response
                    if "{" not in response_text:
                         return response_text
                    return "I encountered an error processing my internal plan. Please try again."

                # Log the thought process
                if self.audit:
                    await self.audit.log_event(
                        session_id=session_id,
                        event_type="sgr_plan",
                        content=plan.model_dump_json(),
                        metadata={"turn": turn}
                    )

                # 2. Execute Logic based on NextAction
                if plan.next_action == NextAction.FINALIZE_RESPONSE:
                    return plan.final_response or "I have completed the task."
                
                elif plan.next_action == NextAction.ASK_USER:
                    return plan.final_response or "Could you please clarify?"

                elif plan.next_action == NextAction.CALL_TOOL:
                    # Execute the first step that has a tool
                    tool_step = next((s for s in plan.steps if s.tool_name), None)
                    
                    if not tool_step:
                        logger.warning("SGR planned CALL_TOOL but no step had a tool_name.")
                        # Fallback to finalize to avoid loop
                        return plan.final_response or "I intended to use a tool but couldn't determine which one."

                    logger.info(f"Executing tool: {tool_step.tool_name}")
                    
                    # Execute Tool
                    tool_result = await self.tools.execute_tool(
                        tool_name=tool_step.tool_name,
                        tool_args=tool_step.tool_args or {}
                    )
                    
                    # Add result to history
                    current_history.append({"role": "assistant", "content": response_text})
                    current_history.append({
                        "role": "user", 
                        "content": f"Tool '{tool_step.tool_name}' Output: {json.dumps(tool_result)}"
                    })
                    
                    # Continue to next turn
                    continue
                
            except Exception as e:
                logger.error(f"Error in SGR loop: {e}")
                return f"I encountered an internal error: {str(e)}"

        return "I reached the maximum number of reasoning steps without a final answer."
