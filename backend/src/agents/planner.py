"""
Planner Agent

This module implements a PlannerAgent that uses the project's LLM client
to decompose a user query into a small plan of steps that use available tools.

The agent returns a JSON structure containing a `goal` and a list of `steps`.
Each step contains: `tool_name`, `args`, and `reasoning`.
"""
from __future__ import annotations

import json
import logging
from typing import List, Dict, Any, Optional

from pydantic import ValidationError

from src.llm import LLMClient
from src.schemas.plan_models import PlanResult, PlanStep
from src.config import settings

logger = logging.getLogger(__name__)


# Note: PlanStep and PlanResult are imported from src.schemas.plan_models


class PlannerAgent:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        # Prefer an injected LLM client; otherwise create one from settings
        if llm_client is None:
            try:
                llm_client = LLMClient()
            except Exception as e:
                logger.warning(f"PlannerAgent: failed to create LLMClient: {e}")
                llm_client = None
        self.llm = llm_client

    async def create_plan(self, user_query: str, available_tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a plan given the user's query and the available tools.

        Returns a dict shaped like {"goal": str, "steps": [ {tool_name, args, reasoning} ]}
        """
        if not self.llm:
            raise RuntimeError("No LLM available for planning")

        tools_list = available_tools or []
        tools_str = "\n".join([f"- {t.get('name')}: {t.get('description','')}" for t in tools_list])

        system_prompt = (
            "You are a PLANNER. Break the user's request into atomic steps using ONLY the available tools. "
            "Output pure JSON with fields 'goal' and 'steps'. 'steps' is an array of objects with 'tool_name', 'args' and 'reasoning'. "
            "Use tool names exactly as provided. If a step needs no tool, place tool_name as 'none' and args as {}. "
            "Do not add any other exposition; return only a valid JSON object."
        )

        instruction = (
            f"Available tools:\n{tools_str}\n\nUser Request:\n{user_query}\n\n"
            "Output a JSON object with 'goal' and 'steps' (tool_name, args, reasoning)."
        )

        # Try up to N times to get a valid JSON plan from the model.
        # Re-prompt the LLM if parse/validation fails.
        max_retries = 3
        last_raw = None
        for attempt in range(max_retries):
            try:
                raw = await self.llm.generate(prompt=instruction, system_prompt=system_prompt)
            except Exception as e:
                logger.exception("PlannerAgent: LLM failed to generate plan")
                return {"goal": user_query, "steps": []}

            last_raw = raw
            # Resilient parse: find first '{' and last '}' and extract JSON
            try:
                if isinstance(raw, str) and '{' in raw and '}' in raw:
                    first = raw.find('{')
                    last = raw.rfind('}')
                    json_str = raw[first:last+1]
                    parsed = json.loads(json_str)
                else:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                parsed = None

            if parsed is None:
                # If parse failed, craft a repair-system prompt for the next attempt
                instruction = (
                    f"Available tools:\n{tools_str}\n\nUser Request:\n{user_query}\n\n"
                    "The previous assistant output was not valid JSON. Return only a valid JSON object with 'goal' and 'steps'. "
                )
                continue

            # Validate parsed structure using PlanResult pydantic model
            try:
                # Normalization: translate fields into expected shape when useful
                # Accept alternative keys like 'plan' or 'tool' by transforming
                normalized = {
                    'goal': parsed.get('goal') or user_query,
                    'steps': []
                }
                raw_steps = parsed.get('steps', parsed.get('plan', []))
                invalid_missing_tool = False
                for s in raw_steps:
                    has_tool_name = 'tool_name' in s or 'tool' in s
                    tn = s.get('tool_name') or s.get('tool') or 'none'
                    args = s.get('args') or s.get('parameters') or {}
                    reasoning = s.get('reasoning') or s.get('note') or ''
                    # If the step doesn't explicitly specify a tool (tool_name/tool), consider this invalid and request a repair
                    if not has_tool_name:
                        invalid_missing_tool = True
                    normalized['steps'].append({"tool_name": tn, "args": args, "reasoning": reasoning})

                if invalid_missing_tool:
                    raise ValueError("Plan step provided args but missing tool_name")

                plan_obj = PlanResult.parse_obj(normalized)
                # Validate steps tools against available tools if provided
                if tools_list:
                    allowed = {t.get('name') for t in tools_list if t.get('name')}
                    invalid_tools = [s.tool_name for s in plan_obj.steps if s.tool_name not in allowed and s.tool_name != 'none']
                    if invalid_tools:
                        raise ValueError(f"Plan contained tools not in available tools: {invalid_tools}")
                # Passed validation: return canonical dict
                return plan_obj.dict()
            except (ValidationError, Exception) as ve:
                logger.warning("PlannerAgent: validation failed on model output; retrying: %s", ve)
                # Re-prompt the LLM on next loop iteration
                instruction = (
                    f"Available tools:\n{tools_str}\n\nUser Request:\n{user_query}\n\n"
                    "Your previous output did not satisfy the required JSON schema. Please return a pure JSON document matching the schema."
                )
                continue

        # If we got here, we failed to produce a valid plan after retries; fall back to a minimal plan
        logger.warning("PlannerAgent: Failed to produce valid plan after %s attempts. Raw last output: %s", max_retries, last_raw)
        return {"goal": user_query, "steps": []}


__all__ = ["PlannerAgent", "PlanResult", "PlanStep"]
