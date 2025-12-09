import pytest
from src.context import ContextManager


class DummyMemory:
    pass


class DummyLLM:
    pass


def test_memory_is_allowed_committed():
    cm = ContextManager(DummyMemory(), DummyLLM())
    mem = {
        'id': '1',
        'content': 'We did something',
        'metadata': {'status': 'committed', 'app_id': 'app-1', 'source': 'neo4j'}
    }
    assert cm._memory_is_allowed(mem)


def test_memory_is_blocked_thinking_content():
    cm = ContextManager(DummyMemory(), DummyLLM())
    mem = {
        'id': '2',
        'content': 'This is thinking_content: pondering ideas',
        'metadata': {'source': 'combined_text'}
    }
    assert not cm._memory_is_allowed(mem)


def test_memory_allowed_by_app_id_even_no_status():
    cm = ContextManager(DummyMemory(), DummyLLM())
    mem = {
        'id': '3',
        'content': 'A useful memory',
        'metadata': {'app_id': 'app-2', 'source': 'user_import'}
    }
    assert cm._memory_is_allowed(mem)
