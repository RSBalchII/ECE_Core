import asyncio
import pytest
from src.distiller_impl import distill_moment

class FakeLLM:
    async def generate(self, text):
        raise RuntimeError("LLM should not be called for code/log paths")

@pytest.mark.asyncio
async def test_distill_skips_llm_for_code_path():
    text = "Exception in thread main at /opt/project/service.py:123\nTraceback (most recent call last): ..."
    fake = FakeLLM()
    res = await distill_moment(text, llm_client=fake, metadata={'path': '/var/log/myapp.log'})
    assert 'summary' in res
    assert isinstance(res['summary'], str)
    assert len(res['summary']) > 0
    assert isinstance(res['entities'], list)
    # Should not be empty because file path and exception should produce entities
    assert len(res['entities']) >= 1
