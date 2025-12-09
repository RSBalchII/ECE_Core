import pytest
from fastapi.testclient import TestClient
import sys, types
from src.app_factory import create_app_with_routers

# Ensure we don't import a broken prompts module — patch a minimal implementation
fake_prompts = types.ModuleType('src.prompts')
def _fake_build_system_prompt(*args, **kwargs):
    return "System prompt"
fake_prompts.build_system_prompt = _fake_build_system_prompt
sys.modules['src.prompts'] = fake_prompts
from src.tools import ToolExecutor


class FakeLLM:
    async def generate(self, prompt, system_prompt=None, **kwargs):
        # Direct answer from memory
        return "Coda is a test entity from memory."


class FakeToolParser:
    class Parsed:
        def __init__(self):
            self.has_tool_calls = False
            self.tool_calls = []

    def parse_response(self, resp):
        return FakeToolParser.Parsed()


class DummyMemory:
    async def get_summaries(self, session_id, limit=8):
        return "HIST_SUM"

    async def get_active_context(self, session_id):
        return "User: hi\nAssistant: hello"

    async def search_memories_neo4j(self, query_text, limit=10):
        return []

    async def get_recent_by_category(self, category, limit=3):
        return []

    def count_tokens(self, text):
        return len(text.split())


def test_chat_prefers_memory_over_tools(monkeypatch):
    app = create_app_with_routers()
    with TestClient(app) as client:
        # Patch memory to include an explicit memory for 'Coda'
        # We'll ensure context contains the memory by patching context_mgr.distiller
        client.app.state.memory = DummyMemory()
        client.app.state.llm = FakeLLM()
        client.app.state.tool_parser = FakeToolParser()
        # Assert ToolExecutor.execute is not invoked when LLM returns a memory-based answer.
        async def _assert_no_tools(self, parsed_response, full_context, request, system_prompt, context_mgr):
            # Ensure parsed_response is None or indicates no tool calls
            assert not (parsed_response and getattr(parsed_response, 'has_tool_calls', False)), "ToolExecutor received a parsed response with tool calls"
            return None, 0, 0
        monkeypatch.setattr(ToolExecutor, "execute", _assert_no_tools)

        # Patch distiller to return a relevant memory that answers the query
        async def fake_filter_and_consolidate(query, memories, summaries, active_context):
            return {
                "summaries": summaries,
                "relevant_memories": "Coda is a test entity from memory.",
                "active_context": active_context,
            }

        client.app.state.context_mgr.distiller.filter_and_consolidate = fake_filter_and_consolidate

        headers = {"Authorization": "Bearer testkey"}
        payload = {"session_id": "s1", "message": "Who is Coda?"}
        resp = client.post("/chat", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "Coda is a test entity from memory." in data["response"]
