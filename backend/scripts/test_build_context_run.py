import sys
sys.path.insert(0, r'c:/Users/rsbiiw/Projects/Context-Engine/ece-core')
from src.context import ContextManager
import asyncio

class DummyMemory:
    def __init__(self):
        self.vector_adapter = None
    async def get_summaries(self, session_id, limit=5):
        return ['Summary 1', 'Summary 2']
    async def get_active_context(self, session_id):
        return 'User: earlier conversation'
    def count_tokens(self, text):
        return len(text)//4
    async def search_memories_neo4j(self, query_text, limit=10):
        return [{'id': '101', 'content': 'We planned a trip to Lake District in July', 'metadata': {'status':'committed', 'app_id':'app-1', 'source':'neo4j'}, 'category':'event', 'importance': 8, 'timestamp':'2025-11-25T00:00:00Z'}]

class DummyLLM:
    async def get_embeddings(self, query):
        return [[0.1, 0.2]]

cm = ContextManager(DummyMemory(), DummyLLM())
ctx = asyncio.run(cm.build_context('session1', 'Tell me about July 2025'))
print('context_part_preview:\n', ctx[:800])
