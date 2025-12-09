import pytest
import asyncio
from src.graph import MarkovianReasoner


class FakeLLM:
    def __init__(self):
        self.count = 0

    async def generate(self, prompt: str, **kwargs) -> str:
        self.count += 1
        # On first chunk, return a non-complete step
        if self.count == 1:
            return "Step 1: do X\nNO\nSummary: Start with X"
        # On second chunk, mark as complete
        if self.count == 2:
            return "YES\nAnswer or Reasoning: The task can be completed by doing X and Y."
        return "NO\nSummary: still thinking"


@pytest.mark.asyncio
async def test_markovian_reasoner_completes_early():
    llm = FakeLLM()
    reasoner = MarkovianReasoner(llm)
    answer = await reasoner.reason("Do the task X", initial_context="")
    assert "The task can be completed" in answer
