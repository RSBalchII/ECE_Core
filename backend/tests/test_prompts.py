import pytest
from src.prompts import build_system_prompt, build_coda_persona_prompt, build_summarization_prompt, build_entity_extraction_prompt


def test_build_system_prompt_no_tools():
    prompt = build_system_prompt(tools_available=False, tools_list=[])
    assert "CURRENT DATE & TIME" in prompt
    assert "Working with Memory and Context" in prompt or "Working with memory" in prompt
    assert "TOOLS" not in prompt.upper()


def test_build_system_prompt_with_tools():
    tools_list = [
        {
            "name": "filesystem_list_directory",
            "description": "List files in a directory",
            "inputSchema": {"properties": {"path": {"type": "string"}}}
        }
    ]
    prompt = build_system_prompt(tools_available=True, tools_list=tools_list)
    assert "AVAILABLE TOOLS" in prompt
    assert "filesystem_list_directory(path" in prompt or "filesystem_list_directory(" in prompt


def test_build_coda_persona_prompt_contains_keywords():
    persona = build_coda_persona_prompt()
    assert "Coda C-001" in persona
    assert "Kaizen" in persona


def test_summarization_prompt_and_entity_extraction():
    text = "Today we released a new feature for the project: improved memory indexing. It uses Redis and Neo4j."
    summ = build_summarization_prompt(text, max_tokens=50)
    assert "Summarize the following" in summ
    ent = build_entity_extraction_prompt(text)
    assert "Entities (JSON):" in ent
