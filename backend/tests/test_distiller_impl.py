import pytest
from src.distiller_impl import Distiller, DistilledMoment, DistilledEntity


class JsonLLM:
    async def generate(self, prompt, **kwargs):
        # Return JSON string with summary and entities
        return '{"summary":"This is a test summary","entities":["Alice", {"name":"Bob"}]}'


@pytest.mark.asyncio
async def test_distiller_parses_json_from_llm():
    llm = JsonLLM()
    d = Distiller(llm_client=llm)
    result = await d.distill_moment("Alice and Bob did a thing.")
    assert isinstance(result, dict)
    assert result["summary"] == "This is a test summary"
    assert any(e for e in result["entities"] if e["text"].lower() == "alice")


@pytest.mark.asyncio
async def test_filter_and_consolidate_active_context_compatibility():
    d = Distiller(llm_client=None)
    memories = [{"content": "Find sand in the yard", "id": "m1"}, {"content": "Another thing", "id": "m2"}]
    summaries = [{"summary": "A summary"}]
    out1 = await d.filter_and_consolidate("yard", memories, summaries, active_turn="User said yard")
    out2 = await d.filter_and_consolidate("yard", memories, summaries, active_context="User said yard")
    assert "active_context" in out1
    assert out1 == out2
