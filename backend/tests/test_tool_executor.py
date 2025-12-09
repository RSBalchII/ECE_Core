import pytest
import asyncio

from src.tools import ToolExecutor


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt: str, system_prompt: str = None):
        self.calls.append({'prompt': prompt, 'system_prompt': system_prompt})
        return "Assistant: Here is the final answer."


class FakeAuditLogger:
    def __init__(self):
        self.logged = []

    def log_tool_call(self, session_id, tool_name, arguments, result):
        self.logged.append({'session_id': session_id, 'tool_name': tool_name, 'arguments': arguments, 'result': result})


class FakePluginManager:
    def __init__(self):
        self.enabled = True

    def lookup_plugin_for_tool(self, tool_name):
        return "demo" if tool_name == "demo_tool" else None

    async def execute_tool(self, name, **kwargs):
        return {"status": "ok", "result": f"Executed {name}"}

    def list_tools(self):
        return [{"name": "demo_tool", "description": "Demo tool", "inputSchema": {"properties": {}}}]


class FakeToolValidator:
    def validate(self, tc):
        return True, None


@pytest.mark.asyncio
async def test_tool_executor_invalid_tool_call():
    llm = FakeLLM()
    audit = FakeAuditLogger()
    pm = FakePluginManager()
    mc = None
    tp = None
    # Validator rejects
    class RejectValidator:
        def validate(self, tc):
            return False, "Invalid"

    tv = RejectValidator()
    tool_executor = ToolExecutor(pm, mc, tp, tv, llm, audit, max_iterations=1)
    parsed = ParsedResponse()
    parsed.tool_calls.append(ToolCall('demo_tool', {}))
    class Req:
        session_id = 's2'
    response, iterations, t_tools_ms = await tool_executor.execute(parsed, full_context="context", request=Req(), system_prompt="sp", context_mgr=None)
    assert "Tool call failed" in response or "Assistant" in response


class ParsedResponse:
    def __init__(self):
        self.has_tool_calls = True
        self.tool_calls = []


class ToolCall:
    def __init__(self, tool_name, parameters=None):
        self.tool_name = tool_name
        self.parameters = parameters or {}


@pytest.mark.asyncio
async def test_tool_executor_executes_plugin_tool():
    llm = FakeLLM()
    audit = FakeAuditLogger()
    pm = FakePluginManager()
    mc = None
    tp = None
    tv = FakeToolValidator()
    tool_executor = ToolExecutor(pm, mc, tp, tv, llm, audit, max_iterations=2)

    parsed = ParsedResponse()
    parsed.tool_calls.append(ToolCall('demo_tool', {}))

    class Req:
        session_id = 's1'

    response, iterations, t_tools_ms = await tool_executor.execute(parsed, full_context="context", request=Req(), system_prompt="sp", context_mgr=None)
    assert "Assistant: Here" in response
    assert iterations >= 1
    assert t_tools_ms >= 0
    assert len(audit.logged) >= 1
