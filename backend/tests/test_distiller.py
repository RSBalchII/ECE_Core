import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.distiller_impl import Distiller

@pytest.mark.asyncio
async def test_distill_moment_success():
    # Mock LLM
    mock_llm = MagicMock()
    # Ensure generate is an AsyncMock
    mock_llm.generate = AsyncMock(return_value='{"summary": "Test summary", "entities": [{"name": "TestEntity", "type": "Concept", "description": "A test entity"}]}')
    
    distiller = Distiller(mock_llm)
    result = await distiller.distill_moment("Some text content")
    
    assert result["summary"] == "Test summary"
    assert len(result["entities"]) == 1
    # Normalized entity key should be 'text' for DistilledEntity
    assert result["entities"][0]["text"] == "TestEntity"

@pytest.mark.asyncio
async def test_distill_moment_json_error():
    # Mock LLM returning invalid JSON
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value='Invalid JSON output')
    
    distiller = Distiller(mock_llm)
    result = await distiller.distill_moment("Some text content")
    
    assert "Error distilling chunk" in result["summary"]
    assert result["entities"] == []

@pytest.mark.asyncio
async def test_distill_moment_no_llm():
    distiller = Distiller(None)
    result = await distiller.distill_moment("Some text content")
    
    assert "..." in result["summary"]
    assert result["entities"] == []

@pytest.mark.asyncio
async def test_annotate_chunk_compatibility():
    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value='{"summary": "Summary", "entities": [{"name": "Ent1", "type": "T", "description": "D"}]}')
    
    distiller = Distiller(mock_llm)
    annotation = await distiller.annotate_chunk("Text")
    
    assert "Summary" in annotation
    assert "Ent1" in annotation


@pytest.mark.asyncio
async def test_filter_and_compact_summary():
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value='{"summary": "S", "entities": [{"name":"E1"}]}')
    distiller = Distiller(mock_llm)
    memories = [{"id":"m1","content":"This is a memory about Project X","importance":5}]
    summaries = [{"summary":"Previously discussed tasks for Project X"}]
    filtered = await distiller.filter_and_consolidate("Project X status", memories, summaries, "Active turn here")
    assert "summaries" in filtered
    assert "relevant_memories" in filtered
    compact = await distiller.make_compact_summary(memories, summaries, "Active turn here", "New input here")
    assert isinstance(compact, str)
