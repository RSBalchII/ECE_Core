import pytest
import asyncio
from src.graph import GraphReasoner


class FakeLLM:
    def __init__(self, mapping=None):
        # mapping of substrings to response
        self.mapping = mapping or {}

    async def generate(self, prompt, **kwargs):
        for key, val in self.mapping.items():
            if key in (prompt or ""):
                return val
        # default: return a non-confident answer
        return "Confidence: LOW\nAnswer or Reasoning: Not enough info"


class FakeMemory:
    def __init__(self):
        pass

    async def get_summaries(self, session_id, limit=3):
        return [{"summary": "Previous chat summary", "timestamp": "2025-01-01T00:00:00Z"}]

    async def execute_cypher(self, query, params=None):
        # return a simple record mimicking Cypher result
        return [{"content": "Important memory content", "score": 1.0, "type": "moment", "id": "m1"}]


@pytest.mark.asyncio
async def test_graph_reasoner_returns_high_confidence_on_first_attempt():
    # Map generate responses to prompt types
    fake_map = {
        "What should you focus on next?": "Focus on trouble area",
        "Generate a concise search query": "important memory",
        "Can you answer the question with HIGH confidence": "Confidence: HIGH\nAnswer or Reasoning: Found answer"
    }
    fake_llm = FakeLLM(mapping=fake_map)
    fake_mem = FakeMemory()
    gr = GraphReasoner(memory=fake_mem, llm=fake_llm)

    res = await gr.reason(session_id="s1", question="What's the important memory?")
    assert res["confidence"] == "high"
    assert "Found answer" in res["answer"]
    assert "reasoning_trace" in res
    assert res["iterations"] == 1


@pytest.mark.asyncio
async def test_graph_reasoner_fallback_final_attempt_when_no_confident_answer():
    # Fake LLM returns low confidence always
    fake_llm = FakeLLM(mapping={"What should you focus on next?": "Focus on nothing"})
    fake_mem = FakeMemory()
    gr = GraphReasoner(memory=fake_mem, llm=fake_llm)
    res = await gr.reason(session_id="s1", question="Unanswerable question")
    assert res["confidence"] in ("medium", "low")
    assert "answer" in res
