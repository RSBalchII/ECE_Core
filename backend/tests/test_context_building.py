import pytest
import asyncio
import sys
import os
local_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if 'src' in sys.modules:
    del sys.modules['src']
sys.path.insert(0, local_src_path)
import importlib
src = importlib.import_module('src')
from src.context import ContextManager


class DummyMemory:
    def __init__(self):
        self._summaries = "This is a summary"
        self._active = "User: hello\nAssistant: hi"

    async def get_summaries(self, session_id, limit=8):
        return self._summaries

    async def get_active_context(self, session_id):
        return self._active

    async def save_active_context(self, session_id, content):
        self._active = content

    # minimal token counting for tests
    def count_tokens(self, text):
        return len(text.split())


class DummyLLM:
    async def get_embeddings(self, text):
        return [[0.0] * 8]

    async def generate(self, prompt, **kwargs):
        return ""


class DummyDistiller:
    async def filter_and_consolidate(self, query, memories, summaries, active_context):
        return {
            "summaries": "HIST_SUM",
            "relevant_memories": "MEMORY: Coda is a test",
            "active_context": active_context,
        }

    async def make_compact_summary(self, *args, **kwargs):
        return "COMPACT_SUM"


@pytest.mark.asyncio
async def test_build_context_places_retrieved_memory_after_user_query(monkeypatch):
    mem = DummyMemory()
    llm = DummyLLM()
    ctx_mgr = ContextManager(memory=mem, llm=llm)

    # Patch Distiller and _retrieve_relevant_memories
    ctx_mgr.distiller = DummyDistiller()

    async def fake_retrieve(_query, limit=10):
        return "MEMORY: Coda is a test"

    monkeypatch.setattr(ctx_mgr, "_retrieve_relevant_memories", fake_retrieve)

    session_id = "test-session"
    user_input = "Do you remember Coda?"
    # Sanity check: Distiller returns relevant memory
    data = await ctx_mgr.distiller.filter_and_consolidate(query=user_input, memories=[], summaries=mem._summaries, active_context=mem._active)
    assert data.get("relevant_memories") is not None

    context_str = await ctx_mgr.build_context(session_id, user_input)

    # Ensure we have the tag and ordering (user query appears before retrieved_memory)
    assert "# What the User Just Said:" in context_str
    assert "<retrieved_memory>" in context_str
    assert context_str.index("# What the User Just Said:") < context_str.index("<retrieved_memory>")
