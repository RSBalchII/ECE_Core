import asyncio
import pytest
from src.context import ContextManager


class FakeLLM:
    async def generate(self, *args, **kwargs):
        return "OK"


class FakeMemory:
    def __init__(self, mems):
        self.mems = mems

    async def search_memories_neo4j(self, query_text: str, limit: int = 10):
        # return all memories that have query_text in content
        results = [m for m in self.mems if query_text.lower() in m['content'].lower()]
        return results[:limit]

    async def get_recent_by_category(self, category: str, limit: int = 10):
        # return top by importance
        return sorted(self.mems, key=lambda x: x.get('importance', 0), reverse=True)[:limit]

    async def get_summaries(self, session_id: str, limit: int = 5):
        return []

    async def get_active_context(self, session_id: str):
        return ""

    async def save_active_context(self, session_id: str, context: str):
        self.saved_context = context


@pytest.mark.asyncio
async def test_retrieval_rerank_by_similarity():
    # Two memories: one more semantically similar to the query
    mems = [
        {"id": "1", "content": "This is about apples and gardening.", "importance": 5, "created_at": "2025-01-01"},
        {"id": "2", "content": "Coda project: details about design and context management in code.", "importance": 5, "created_at": "2025-11-11"},
        {"id": "3", "content": "Random note unrelated to query.", "importance": 1, "created_at": "2024-01-01"}
    ]

    fake_memory = FakeMemory(mems)
    fake_llm = FakeLLM()
    cm = ContextManager(memory=fake_memory, llm=fake_llm)

    res = await cm._retrieve_relevant_memories("Coda project design", limit=3)
    # Expect the Coda project memory to be first due to higher overlap
    assert len(res) > 0
    assert res[0]["id"] == "2"

@pytest.mark.asyncio
async def test_build_context_appends_distiller_summary():
    mems = [
        {"id": "1", "content": "Coda project: design notes and architecture.", "importance": 6, "created_at": "2025-11-11", "category": "project"},
    ]
    fake_memory = FakeMemory(mems)
    fake_llm = FakeLLM()
    cm = ContextManager(memory=fake_memory, llm=fake_llm)
    # current active context empty
    await cm.build_context("session_test", "Tell me about Coda project architecture")
    # The Distiller summary should have been appended at least once
    assert hasattr(fake_memory, 'saved_context'), "Distiller summary not saved to active context"
    assert "Tell me about Coda project architecture" in fake_memory.saved_context
