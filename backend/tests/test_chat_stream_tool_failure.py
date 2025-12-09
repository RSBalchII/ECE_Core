import pytest
from fastapi.testclient import TestClient
from src.app_factory import create_app_with_routers
from src.tool_call_models import ToolCallValidator


class FakeLLM:
    async def generate(self, prompt, system_prompt=None, **kwargs):
        return "[FAKE-LLM-FINAL] Response after tool error"

    async def stream_generate(self, prompt, system_prompt=None):
        # Emit a single chunk that includes a TOOL_CALL expression
        yield "TOOL_CALL: demo_tool()"

    # Add embedding method used by context_manager and other code paths
    async def get_embeddings_for_documents(self, docs):
        # return a simple deterministic embedding vector per document
        return [[0.0] * 8 for _ in docs]

    async def get_embeddings(self, text):
        return [0.0] * 8


class FakePluginManager:
    def __init__(self):
        self.enabled = True

    def discover(self):
        return ['demo_plugin']

    def list_tools(self):
        return [{"name": "demo_tool", "description": "Demo tool", "inputSchema": {"properties": {}}}]

    def lookup_plugin_for_tool(self, tool_name):
        return "demo_plugin" if tool_name == "demo_tool" else None

    async def execute_tool(self, name, **kwargs):
        # Simulate tool failure by raising
        raise Exception("Simulated plugin execution failure")


class FakeAuditLogger:
    def __init__(self):
        self.logged = []

    def log_tool_call(self, session_id, tool_name, arguments, result):
        self.logged.append({'session_id': session_id, 'tool_name': tool_name, 'arguments': arguments, 'result': result})


def test_chat_stream_handles_tool_executor_exception(monkeypatch):
    app = create_app_with_routers()

    with TestClient(app) as client:
        # Patch components to use fakes after app startup so lifespans don't override
        client.app.state.llm = FakeLLM()
        client.app.state.plugin_manager = FakePluginManager()
        client.app.state.tool_parser = client.app.state.tool_parser  # keep the real parser
        # Provide a tool validator so ToolExecutor runs
        tool_map = {"demo_tool": {"inputSchema": {"properties": {}}}}
        client.app.state.tool_validator = ToolCallValidator(tool_map)
        client.app.state.audit_logger = FakeAuditLogger()
        headers = {"Authorization": "Bearer testkey"}
        payload = {"session_id": "s1", "message": "Find memories about July 2025", "system_prompt": None}
        # Post (TestClient wraps the ASGI call) and read streaming response via iter_lines
        resp = client.post("/chat/stream", json=payload, headers=headers)
        assert resp.status_code == 200
        data = ""
        for line in resp.iter_lines():
                if line:
                    try:
                        # decode bytes
                        chunk = line.decode('utf-8') if isinstance(line, (bytes, bytearray)) else str(line)
                    except Exception:
                        chunk = str(line)
                    data += chunk + "\n"
        # Debug prints removed; data parsed below

    # The streamed data should include the 'thinking:' label and either tool failure text or the LLM fallback response
    import json as _json
    assert "thinking:" in data
    # We expect a response label and final response chunks; parse JSON chunks and reconstruct final response
    parsed_chunks = []
    for line in data.splitlines():
        line = line.strip()
        if not line or not line.startswith("data: "):
            continue
        try:
            obj = _json.loads(line[len("data: "):])
            if 'chunk' in obj:
                parsed_chunks.append(obj['chunk'])
        except Exception:
            continue

    assert any('response' in c for c in parsed_chunks)
    # Reconstruct the final response by joining the chunks after the 'response' marker
    final_idx = 0
    for i, c in enumerate(parsed_chunks):
        if isinstance(c, str) and 'response' in c:
            final_idx = i + 1
            break
    final_response_text = ''.join(parsed_chunks[final_idx:])
    # The fallback should include the standardized '[ToolExecutionFallback]' tag from ToolExecutor or stream fallback
    assert '[ToolExecutionFallback]' in final_response_text
