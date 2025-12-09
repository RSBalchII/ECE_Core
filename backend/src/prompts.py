"""Minimal and robust prompt utilities for ECE Core.

This file intentionally contains a single, minimal `build_system_prompt`
implementation and the small helper functions used in tests. The goal is to
remain tiny, explicit, and stable so runtime loading and tests are reliable.
"""
from datetime import datetime, timezone
import os
from typing import List, Dict, Optional


def build_system_prompt(
    tools_available: bool = False,
    tools_list: Optional[List[Dict]] = None,
    current_datetime: Optional[datetime] = None,
) -> str:
    """Return a concise system prompt emphasizing memory-first guidance.

    The prompt includes a short header, a 'memory-first' guidance, a concise
    instruction on tools, and an optional tools list when `tools_available` is
    True.
    """
    if current_datetime is None:
        current_datetime = datetime.now(timezone.utc)
    # If an explicit CODA_SYSTEM_PROMPT is provided via env (or YAML), prefer that as the system prompt.
    sys_prompt_env = os.getenv('CODA_SYSTEM_PROMPT')
    if sys_prompt_env:
        return sys_prompt_env
    current_date = current_datetime.strftime("%Y-%m-%d")
    current_time = current_datetime.strftime("%H:%M UTC")

    prompt = [f"**CURRENT DATE & TIME: {current_date} {current_time}**"]
    prompt.append("You are an AI assistant with access to the user's personal memory and context.")
    prompt.append("Working with Memory and Context:")
    prompt.append("- Check <retrieved_memory> and <memory> blocks FIRST for recall/summary queries; ONLY treat information enclosed within <memory>...</memory> as verified factual history; if the answer is present there, DO NOT use a tool.")
    prompt.append("- Use tools for real-time external data (web, filesystem, system state) or when memory lacks the needed information.")
    prompt.append("- When invoking a tool, put the tool call on its own line as: TOOL_CALL: tool_name(param1=value1)")
    prompt.append("- IMPORTANT: Do not output chain-of-thought or internal analysis to the user. Use internal channels for thoughts only and produce a single clear final response in natural conversational form. If diagnostics are required, place them in a 'thinking:' channel only when explicitly asked for diagnostics.")

    # SIMPLE HARNESS PROTOCOL
    prompt.append("\n[SIMPLE HARNESS PROTOCOL]")
    prompt.append("If you need to use a basic tool, you may output a single line in one of the following forms (do NOT use XML/JSON for these basic actions):")
    prompt.append("Action: search web query=\"...\"")
    prompt.append("Action: read file path=\"...\"")
    prompt.append("Action: execute cmd command=\"...\"")
    prompt.append("These lines are machine-processable and meant only for deterministic tool calls for small models. If you produce an 'Action:' line, do NOT include extra text on that line.")

    if tools_available and tools_list:
        prompt.append("\n**AVAILABLE TOOLS:**")
        for tool in tools_list:
            name = tool.get('name') if isinstance(tool, dict) else getattr(tool, 'name', 'UNKNOWN')
            desc = tool.get('description', '') if isinstance(tool, dict) else getattr(tool, 'description', '')
            params = ''
            if isinstance(tool, dict) and 'inputSchema' in tool and isinstance(tool['inputSchema'], dict):
                props = tool['inputSchema'].get('properties', {})
                params = ", ".join(props.keys())
            prompt.append(f"- {name}({params}): {desc}")

    prompt.append("Be concise, factual, and only ground answers in verified memory (<memory> tags) or explicit tool output.")
    return "\n".join(prompt)


def build_coda_persona_prompt() -> str:
    """Return a short persona prompt used for persona-specific conversations.

    Tests assert that the persona contains 'Coda C-001' and 'Kaizen'. Keep
    this minimal and stable.
    """
    return (
        "You are Coda C-001, a memory-augmented AI assistant.\n\n"
        "Core Philosophy: Kaizen (continuous improvement); Chutzpah; Shoshin.\n"
        "Communication: Concise, candid, and helpful."
    )


def build_summarization_prompt(text: str, max_tokens: int) -> str:
    return f"Summarize the following into approximately {max_tokens} tokens:\n\n{text}\n\nSummary:"


def build_entity_extraction_prompt(text: str) -> str:
    return (
        "Extract key entities as JSON using categories: PERSON, CONCEPT, PROJECT, CONDITION, SKILL.\n\n"
        f"Text:\n{text}\n\nEntities (JSON):"
    )
