"""Utility helpers for tools/ plugin management and tool listing.

This centralizes tool list formatting for use in the prompt builder and other
places in the app. Moving this out of main reduces duplicated code and keeps
the main module smaller.
"""
from typing import Any, Dict, List, Optional
import json
import time
import logging

logger = logging.getLogger(__name__)


def get_tools_list(plugin_manager: Optional[Any], mcp_client: Optional[Any]):
    """Return a normalized list of tool objects from plugin manager or mcp client.

    Each tool in the returned list will be a dict with keys 'name', 'description', and
    'inputSchema' at a minimum. If no tools found, returns [] and tools_available False.
    """
    tools = []
    try:
        if plugin_manager and getattr(plugin_manager, "enabled", False):
            tools = plugin_manager.list_tools() or []
        elif mcp_client:
            # mcp_client call is async in some paths; callers should handle that
            tools = []
            # We don't call the async MCP client here to keep this helper simple.
    except Exception:
        tools = []

    return tools


def format_tools_for_prompt(tools_list: List[Dict]) -> str:
    """Return a human-readable tools description suitable to append to the system prompt.

    E.g. "- fs_list(path): List files at path"
    """
    if not tools_list:
        return ""
    lines = []
    for tool in tools_list:
        params = ", ".join([p for p in tool.get('inputSchema', {}).get('properties', {}).keys()])
        lines.append(f"- {tool.get('name')}({params}): {tool.get('description','')}")
    out = "**AVAILABLE TOOLS:**\n" + "\n".join(lines) + "\n\nTo use a tool, respond with: TOOL_CALL: tool_name(param1=value1, param2=value2)"
    return out


class ToolExecutor:
    """Responsible for executing tool calls detected in an LLM response.

    This encapsulates validation, execution via plugins or MCP, audit logging,
    and re-generation after tool output.
    """
    def __init__(self, plugin_manager: Optional[Any], mcp_client: Optional[Any], tool_parser: Optional[Any], tool_validator: Optional[Any], llm_client: Optional[Any], audit_logger: Optional[Any], max_iterations: int = 3):
        self.plugin_manager = plugin_manager
        self.mcp_client = mcp_client
        self.tool_parser = tool_parser
        self.tool_validator = tool_validator
        self.llm = llm_client
        self.audit_logger = audit_logger
        self.max_iterations = max_iterations

    async def execute(self, parsed_response, full_context, request, system_prompt, context_mgr):
        """
        Execute tool calls detected in the LLM response.

        Behavior and output flow overview:
        - The LLM's initial text is passed via `initial_response` in the calling endpoint.
        - This executor validates tool calls, executes them via plugin manager or MCP, and then triggers a fresh LLM generation that includes tool results.
        - The returned `response` is the final LLM reply. The caller (chat endpoints) treats this as the 'response:' section, while the initial LLM output remains the 'thinking:' section.
        - Tool output is logged via `audit_logger` (if provided) and appended to the prompt so the LLM can reason with the results.
        """
        iteration = 0
        t_tools_total_ms = 0.0
        response = None

        # Track previous tool calls to detect loops
        previous_tool_calls = set()
        tool_call_counts = {}  # Track count per tool name

        while parsed_response and getattr(parsed_response, 'has_tool_calls', False) and iteration < self.max_iterations and self.tool_validator:
            iteration += 1

            # Check for tool call loops by detecting repeated tool calls with same parameters
            for tc in parsed_response.tool_calls:
                tool_call_key = (tc.tool_name, tuple(sorted(tc.parameters.items())))
                if tool_call_key in previous_tool_calls:
                    logger.warning(f"Detected tool call loop: {tc.tool_name} with same parameters")
                    # Break the loop by generating a response without tools
                    tool_ctx = f"\n\nTool call loop detected. You have attempted to call the same tool with the same parameters multiple times. Please answer the user's question directly without further tool calls."
                    response = await self.llm.generate(prompt=full_context + tool_ctx, system_prompt=system_prompt)
                    return response, iteration, t_tools_total_ms
                previous_tool_calls.add(tool_call_key)

                # Track and limit the number of times any single tool can be called
                tool_call_counts[tc.tool_name] = tool_call_counts.get(tc.tool_name, 0) + 1
                if tool_call_counts[tc.tool_name] > 5:  # Limit any single tool to 5 calls per conversation
                    logger.warning(f"Tool call limit reached for {tc.tool_name}: {tool_call_counts[tc.tool_name]} calls")
                    tool_ctx = f"\n\nYou have used the '{tc.tool_name}' tool multiple times. Please provide a final response to the user without using this tool again."
                    response = await self.llm.generate(prompt=full_context + tool_ctx, system_prompt=system_prompt)
                    return response, iteration, t_tools_total_ms

            # Choose first valid tool call
            tool_call = None
            validation_error = None
            for tc in parsed_response.tool_calls:
                if self.tool_validator:
                    is_valid, err = self.tool_validator.validate(tc)
                    if is_valid:
                        tool_call = tc
                        break
                    validation_error = err
                else:
                    tool_call = tc
                    break

            if not tool_call:
                # No valid tool calls; return a helpful response
                error_msg = validation_error or 'No valid tool calls found'
                logger.error(f"Tool call validation failed: {error_msg}")
                tool_ctx = f"\n\nTool call failed: {error_msg}\n\nPlease acknowledge and provide a helpful answer without tools."
                response = await self.llm.generate(prompt=full_context + tool_ctx, system_prompt=system_prompt)
                # Standardized fallback tag for deterministic detection in tests and UI
                response = f"[ToolExecutionFallback] {response}"
                return response, iteration, t_tools_total_ms

            # Execute tool call
            try:
                if self.audit_logger:
                    try:
                        self.audit_logger.log_tool_call(
                            session_id=request.session_id,
                            tool_name=tool_call.tool_name,
                            arguments=tool_call.parameters,
                            result='pending'
                        )
                    except Exception:
                        logger.warning("Failed to write audit log for tool call (pending)")
                t_tool_start = time.perf_counter()
                if self.plugin_manager and getattr(self.plugin_manager, 'enabled', False):
                    plugin_name = self.plugin_manager.lookup_plugin_for_tool(tool_call.tool_name)
                    if plugin_name:
                        tool_result = await self.plugin_manager.execute_tool(f"{plugin_name}:{tool_call.tool_name}", **tool_call.parameters)
                    else:
                        tool_result = {"error": f"Tool not found in plugins: {tool_call.tool_name}"}
                elif self.mcp_client:
                    tool_result = await self.mcp_client.call_tool(tool_call.tool_name, **tool_call.parameters)
                else:
                    tool_result = {"error": "Tools disabled"}
                t_tool_ms = (time.perf_counter() - t_tool_start) * 1000
                t_tools_total_ms += t_tool_ms
                if self.audit_logger:
                    try:
                        self.audit_logger.log_tool_call(
                            session_id=request.session_id,
                            tool_name=tool_call.tool_name,
                            arguments=tool_call.parameters,
                            result=str(tool_result)[:200]
                        )
                    except Exception:
                        logger.warning("Failed to write audit log for tool call (result)")

                # Treat explicit errors and empty/None results as failures and ask the LLM to provide feedback
                if tool_result is None or tool_result == {} or (isinstance(tool_result, (str, list)) and not tool_result) or (isinstance(tool_result, dict) and 'error' in tool_result):
                    # Report either the explicit error or a general 'no output' condition
                    if isinstance(tool_result, dict) and 'error' in tool_result:
                        err_text = tool_result.get('detail', tool_result.get('error'))
                    else:
                        err_text = 'Tool returned no output.'
                    tool_context = f"\n\nTool '{tool_call.tool_name}' failed or returned no output: {err_text}\n\nProvide helpful feedback to the user."
                else:
                    tool_context = f"\n\nTool '{tool_call.tool_name}' returned:\n{json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)}\n\nNow answer the user's question using this information."

                response = await self.llm.generate(prompt=full_context + tool_context, system_prompt=system_prompt)
                parsed_response = self.tool_parser.parse_response(response) if self.tool_parser else None
            except Exception as e:
                logger.error(f"Tool execution failed for {tool_call.tool_name}: {e}")
                response = await self.llm.generate(prompt=full_context + f"\n\nTool execution failed: {e}\n\nAcknowledge and suggest alternatives.", system_prompt=system_prompt)
                # Standardized fallback tag for deterministic detection in tests and UI
                response = f"[ToolExecutionFallback] {response}"
                return response, iteration, t_tools_total_ms

        return response, iteration, t_tools_total_ms

