import pytest
import asyncio

from src.agents.planner import PlannerAgent
from src.schemas.plan_models import PlanResult
from src.app_factory import create_app_with_routers
from fastapi.testclient import TestClient
from src.config import settings


class MockLLM:
    def __init__(self, responses):
        self._responses = responses[:]

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens=None, temperature=None):
        # Return next response; if none left, return an invalid string
        if self._responses:
            return self._responses.pop(0)
        return "I cannot produce a plan"


@pytest.mark.asyncio
async def test_create_plan_valid():
    valid_json = '{"goal": "Find docs", "steps": [{"tool_name": "search", "args": {"query": "docs"}, "reasoning": "Find docs on topic."}]}'
    llm = MockLLM([valid_json])
    agent = PlannerAgent(llm_client=llm)
    plan = await agent.create_plan("Find docs about X", [])
    # Should return a dict where goal is set and steps contains one step
    assert isinstance(plan, dict)
    assert plan["goal"] == "Find docs"
    assert isinstance(plan["steps"], list)
    assert plan["steps"][0]["tool_name"] == "search"


@pytest.mark.asyncio
async def test_create_plan_invalid_then_valid():
    invalid = "I'm thinking about a plan but won't share json"
    valid_json = '{"goal": "Do task", "steps": [{"tool_name": "search", "args": {}, "reasoning": "Search for info"}]}'
    llm = MockLLM([invalid, valid_json])
    agent = PlannerAgent(llm_client=llm)
    plan = await agent.create_plan("Do task now", [])
    assert isinstance(plan, dict)
    assert plan["goal"] == "Do task"
    assert len(plan["steps"]) == 1


@pytest.mark.asyncio
async def test_create_plan_invalid_all_retries():
    responses = ["nope", "still not", "nah"]
    llm = MockLLM(responses)
    agent = PlannerAgent(llm_client=llm)
    plan = await agent.create_plan("Do something", [])
    # Expected fallback minimal plan
    assert plan["goal"] == "Do something"
    assert plan["steps"] == []


@pytest.mark.asyncio
async def test_create_plan_invalid_schema_repair():
    # Missing tool_name field in the step -> should be normalized or cause re-prompt
    bad = '{"goal":"G","steps":[{"args":{}}]}'
    good = '{"goal":"G","steps":[{"tool_name":"search","args":{},"reasoning":"ok"}]}'
    llm = MockLLM([bad, good])
    agent = PlannerAgent(llm_client=llm)
    plan = await agent.create_plan("G", [])
    assert plan["goal"] == "G"
    assert isinstance(plan["steps"], list)
    assert plan["steps"][0]["tool_name"] == "search"


@pytest.mark.asyncio
async def test_create_plan_invalid_tool_then_valid():
    # First response uses a tool name not in available tools -> should be retried
    bad_tool = '{"goal":"T","steps":[{"tool_name":"fake_tool","args":{}}]}'
    good = '{"goal":"T","steps":[{"tool_name":"search","args":{},"reasoning":"ok"}]}'
    llm = MockLLM([bad_tool, good])
    agent = PlannerAgent(llm_client=llm)
    available_tools = [{'name': 'search', 'description': 'Search the web'}]
    plan = await agent.create_plan("T", available_tools)
    assert plan['goal'] == 'T'
    assert plan['steps'][0]['tool_name'] == 'search'


def test_plan_endpoint_should_return_plan(monkeypatch):
    # Create an app instance and inject a PlannerAgent with mock LLM
    app = create_app_with_routers()
    # prevent API key requirement for the test
    monkeypatch.setattr(settings, 'ece_require_auth', False)

    # Minimal valid json plan
    valid_json = '{"goal": "Endpoint Goal", "steps": [{"tool_name": "search", "args": {"query": "X"}}]}'
    mock_llm = MockLLM([valid_json])
    app.state.planner = PlannerAgent(llm_client=mock_llm)

    client = TestClient(app)
    resp = client.post('/plan', json={'session_id': 's1', 'message': 'Find X'})
    assert resp.status_code == 200
    body = resp.json()
    assert 'plan' in body
    assert body['plan']['goal'] == 'Endpoint Goal'
