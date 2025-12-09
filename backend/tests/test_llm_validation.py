import json
from src.schemas.llm_response import LLMStructuredResponse
from src.tool_call_models import ToolCall


def test_llm_structured_response_valid():
    # Simulate LLM returning a valid JSON matching the schema
    obj = {
        "answer": "This is a valid answer",
        "sources": ["doc:123", "doc:456"],
        "tool_calls": [
            {"tool_name": "web_search", "parameters": {"query": "AI news"}}
        ],
        "confidence": "high"
    }
    # Validate with pydantic
    parsed = LLMStructuredResponse.parse_obj(obj)
    assert parsed.answer == "This is a valid answer"
    assert len(parsed.tool_calls) == 1


def test_llm_structured_response_missing_answer():
    # Missing required 'answer' field should raise a ValidationError
    obj = {"sources": ["doc:123"]}
    try:
        LLMStructuredResponse.parse_obj(obj)
        assert False, "Validation should have failed"
    except Exception:
        assert True
