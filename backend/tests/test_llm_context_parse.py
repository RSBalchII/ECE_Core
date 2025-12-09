import pytest
import asyncio
from src.llm import LLMClient


def test_parse_n_ctx_slot():
    c = LLMClient()
    msg = "error: n_ctx_slot = 8192; task.n_tokens = 12000"
    v = c._parse_context_size_from_error(msg)
    assert v == 8192


def test_parse_context_size_key():
    c = LLMClient()
    msg = "request exceeds the available context size (context size: 4096)"
    v = c._parse_context_size_from_error(msg)
    assert v == 4096


def test_parse_task_n_tokens():
    c = LLMClient()
    msg = "task.n_tokens = 10225"  # might indicate tokens present
    v = c._parse_context_size_from_error(msg)
    assert v == 10225


def test_parse_none():
    c = LLMClient()
    msg = "server error without size hints"
    v = c._parse_context_size_from_error(msg)
    assert v is None
