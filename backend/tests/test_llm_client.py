import pytest
import types
from src.llm import LLMClient


class FakeResp:
    def __init__(self, json_data):
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class FakeAsyncClient:
    def __init__(self, json_data=None, raise_exc=False):
        self._json = json_data or {}
        self._raise = raise_exc

    async def get(self, url):
        if self._raise:
            raise Exception("network")
        return FakeResp(self._json)

    async def post(self, url, json=None):
        return FakeResp({"data": [{"embedding": [0.1, 0.2]}]})

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_detect_model_success(monkeypatch):
    c = LLMClient()
    # Inject fake client returning a models list
    c.client = FakeAsyncClient(json_data={"data": [{"id": "gpt-4-mini"}]})
    detected = await c.detect_model()
    assert detected == "gpt-4-mini"


@pytest.mark.asyncio
async def test_detect_model_fallback_on_error(monkeypatch):
    c = LLMClient()
    c.client = FakeAsyncClient(raise_exc=True)
    # Ensure fallback to configured model name
    detected = await c.detect_model()
    assert detected == c.model
import pytest
import asyncio
from src.llm import LLMClient


@pytest.mark.asyncio
async def test_generate_api_fallback(monkeypatch):
    client = LLMClient()

    async def fake_generate_api(prompt, max_tokens, temperature, system_prompt):
        raise Exception("API down")

    # Monkeypatch the API generate and ensure local is used
    monkeypatch.setattr(client, "_generate_api", fake_generate_api)

    class FakeLocalModel:
        def __call__(self, prompt, max_tokens, temperature, top_p, echo):
            return {"choices": [{"text": "local model output"}]}

    client._local_llm = FakeLocalModel()
    client._use_local = True
    res = await client.generate("hello")
    assert isinstance(res, str)
    assert res == "local model output"
