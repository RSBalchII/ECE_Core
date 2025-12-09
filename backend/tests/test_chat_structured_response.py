import pytest
from fastapi.testclient import TestClient
from src.app_factory import create_app_with_routers
from src.tool_call_models import ToolCallValidator


class FakeLLM:
    async def generate(self, prompt, system_prompt=None, **kwargs):
        # Return initial LLM output if asked; but for /chat we call generate only once by default
        return "[FAKE-LLM-INITIAL] My initial thought"


def test_chat_returns_structured_response(monkeypatch):
    app = create_app_with_routers()
    with TestClient(app) as client:
        # Patch components with fake LLM
        client.app.state.llm = FakeLLM()
        client.app.state.tool_parser = client.app.state.tool_parser
        client.app.state.tool_validator = None
        headers = {"Authorization": "Bearer testkey"}
        payload = {"session_id": "s1", "message": "How are my memories?"}
        resp = client.post("/chat", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        text = data.get("response", "")
        assert "thinking:" in text
        assert "response:" in text
