import asyncio
import json
from src.distiller_impl import Distiller
from src.llm import ContextSizeExceededError


class FakeLLM:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt, max_tokens=None, temperature=None, system_prompt=None):
        self.calls += 1
        # First call triggers context size exceeded to force chunking path
        if self.calls == 1:
            raise ContextSizeExceededError("exceeds the available context size", n_ctx=8192, server_message='task.n_tokens = 10225, n_ctx_slot = 8192')
        # Subsequent calls return a small JSON summary
        return json.dumps({"summary": f"Summary-{self.calls}", "entities": ["TestEntity"]})


def test_chunking_flow():
    # Build a long text for chunking
    text = "\n".join(["Sentence repeated to create large text." * 50 for _ in range(40)])
    llm = FakeLLM()
    dist = Distiller(llm_client=llm)
    res = asyncio.run(dist.distill_moment(text))
    assert isinstance(res, dict)
    assert "summary" in res and res["summary"]
    assert isinstance(res.get("entities"), list)
    # Ensure chunk path invoked (calls > 1)
    assert llm.calls > 1
