import pytest
from src.context import ContextManager


class FakeMem:
    def __init__(self):
        self._active = "User: hello\nAssistant: hi"

    async def get_summaries(self, session_id, limit=8):
        return [{"summary": "Old summary"}]

    async def get_active_context(self, session_id):
        return self._active

    async def get_recent_by_category(self, category, limit=3):
        return []

    async def search_memories_neo4j(self, query_text, limit=10, category=None):
        return []

    async def count_tokens(self, text):
        return len(text) // 4

    async def save_active_context(self, session_id, context):
        self._active = context

    # Provide a minimal API used by context manager
    async def get_recent_memories_neo4j(self, category=None, limit=10):
        return []


class FakeLLM:
    async def generate(self, prompt, **kwargs):
        return "Short summary"


class FakeDistiller:
    async def filter_and_consolidate(self, query, memories, summaries, active_context=None, active_turn=None):
        return {"summaries": summaries, "relevant_memories": memories, "active_context": active_context or active_turn}

    async def make_compact_summary(self, memories, summaries, active_context, new_input):
        return "Compact summary"


class FakeChunker:
    async def process_large_input(self, user_input, query_context=""):
        return user_input


@pytest.mark.asyncio
async def test_build_context_includes_sections():
    mem = FakeMem()
    llm = FakeLLM()
    cm = ContextManager(memory=mem, llm=llm)
    # Replace distiller and chunker with fakes
    cm.distiller = FakeDistiller()
    cm.chunker = FakeChunker()
    res = await cm.build_context(session_id="s1", user_input="Hello world")
    assert "Current Date & Time" in res
    assert "What the User Just Said" in res
    assert "Current Conversation" in res
