import pytest
from src.distiller_impl import Distiller


class BrokenLLM:
    async def generate(self, prompt, **kwargs):
        raise RuntimeError("LLM should not be called for token-soup content")


@pytest.mark.asyncio
async def test_distiller_skips_llm_for_token_soup():
    llm = BrokenLLM()
    d = Distiller(llm_client=llm)
    corrupted = "memcpy(dest, src, size); 0xAABBCCDDEEFF1122 7090; func_call(); manualHeaderValue&&&&&&"
    result = await d.distill_moment(corrupted)
    assert isinstance(result, dict)
    assert result.get("summary") is not None
    # Should not call the LLM; verify length and fallback score
    assert result.get("score") == 0.1
    assert len(result.get("entities", [])) >= 0
