import asyncio
import pytest
from src.distiller_impl import distill_moment

class FakeLLMCount:
    def __init__(self):
        self.calls = 0
    async def generate(self, text):
        self.calls += 1
        return {"summary": "Test summary", "entities": ["Thing"]}

@pytest.mark.asyncio
async def test_in_memory_distill_cache_reuse(monkeypatch):
    fake = FakeLLMCount()
    txt = "This is some repeatable content that will be cached."
    # First call should invoke LLM
    res1 = await distill_moment(txt, llm_client=fake, metadata={'source':'unit_test'})
    # Second call should hit cache and not call LLM again
    res2 = await distill_moment(txt, llm_client=fake, metadata={'source':'unit_test'})
    assert fake.calls == 1
    assert res1 == res2

