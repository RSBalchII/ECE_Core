import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# tests/test_ece_tools.py

import pytest
import json
from unittest.mock import MagicMock, patch

# Correct the import path based on the project structure
from src.external_context_engine.tools.ece_tools import (
    DistillerAgent,
    ArchivistAgent,
    ExtractorAgent,
    DistillInput,
    ArchiveInput,
    ExtractInput,
)

# === Mock LLM and DB Manager ===


@pytest.fixture
def mock_llm():
    """Fixture for a mock LLM."""
    llm = MagicMock()
    # Define different return values for different prompts if needed
    llm.invoke.return_value = '{"key": "value"}'  # Default mock value
    return llm


@pytest.fixture
def mock_db_manager():
    """Fixture for a mock DB Manager."""
    with patch("src.external_context_engine.tools.ece_tools.db_manager") as mock_db:
        mock_db.get_schema.return_value = {
            "node_labels": ["Concept"],
            "relationship_types": ["IS_ARCHITECT_FOR", "USES", "IMPLEMENTS"],
        }
        mock_db.execute_query.return_value = [{"result": "mock_data"}]
        yield mock_db


# === Agent Fixtures ===


@pytest.fixture
def distiller_agent(mock_llm):
    """Fixture for a DistillerAgent instance."""
    return DistillerAgent(llm=mock_llm)


@pytest.fixture
def archivist_agent():
    """Fixture for an ArchivistAgent instance."""
    return ArchivistAgent(llm=None)  # No LLM needed for the deterministic archivist


@pytest.fixture
def extractor_agent(mock_llm):
    """Fixture for an ExtractorAgent instance."""
    return ExtractorAgent(llm=mock_llm)


# === Unit Tests ===


def test_distiller_agent(distiller_agent, mock_llm):
    """Test the DistillerAgent's ability to process text."""
    # Arrange
    raw_text = "Rob is the architect for the ECE project."
    expected_json = {
        "entities": ["Rob", "ECE Project"],
        "relationships": [["Rob", "IS_ARCHITECT_FOR", "ECE Project"]],
    }
    mock_llm.invoke.return_value = json.dumps(expected_json)
    tool_input = DistillInput(raw_text=raw_text)

    # Act
    result = distiller_agent._run(tool_input)

    # Assert
    assert json.loads(result) == expected_json
    mock_llm.invoke.assert_called_once()
    assert raw_text in mock_llm.invoke.call_args[0][0]


def test_archivist_agent(archivist_agent, mock_db_manager):
    """Test the ArchivistAgent's ability to persist data."""
    # Arrange
    structured_summary = {
        "entities": ["Coda", "ECE Project"],
        "relationships": [["Coda", "IMPLEMENTS", "ECE Project"]],
    }
    tool_input = ArchiveInput(structured_summary=json.dumps(structured_summary))

    # Act
    result = archivist_agent._run(tool_input)

    # Assert
    assert "Archive complete" in result
    # Check that MERGE was called for entities
    mock_db_manager._driver.session.return_value.run.assert_any_call(
        "MERGE (c:Concept {name: $name})", name="Coda"
    )
    mock_db_manager._driver.session.return_value.run.assert_any_call(
        "MERGE (c:Concept {name: $name})", name="ECE Project"
    )
    # Check that MERGE was called for the relationship
    mock_db_manager._driver.session.return_value.run.assert_any_call(
        "MATCH (a:Concept {name: $source}) MATCH (b:Concept {name: $target}) MERGE (a)-[r:IMPLEMENTS]->(b)",
        source="Coda",
        target="ECE Project",
    )


def test_extractor_agent(extractor_agent, mock_llm, mock_db_manager):
    """Test the ExtractorAgent's ability to query data."""
    # Arrange
    question = "Who is the architect for ECE?"
    generated_cypher = "MATCH (p:Concept {name: 'Rob'})-[r:IS_ARCHITECT_FOR]->(prj:Concept {name: 'ECE Project'}) RETURN p.name"
    mock_llm.invoke.return_value = generated_cypher
    expected_result = [{"p.name": "Rob"}]
    mock_db_manager.execute_query.return_value = expected_result
    tool_input = ExtractInput(question=question)

    # Act
    result = extractor_agent._run(tool_input)

    # Assert
    mock_db_manager.get_schema.assert_called_once()
    mock_llm.invoke.assert_called_once()
    assert question in mock_llm.invoke.call_args[0][0]
    mock_db_manager.execute_query.assert_called_once_with(generated_cypher)
    assert json.loads(result) == expected_result


# === Integration Test ===


def test_end_to_end_workflow(
    distiller_agent, archivist_agent, extractor_agent, mock_llm, mock_db_manager
):
    """An integration test for the full Distill -> Archive -> Extract workflow."""
    # --- 1. Distill Phase ---
    # Arrange
    raw_text = "Coda is an agent that implements the ECE Project, which uses Neo4j."
    distill_json_str = json.dumps(
        {
            "entities": ["Coda", "ECE Project", "Neo4j"],
            "relationships": [
                ["Coda", "IMPLEMENTS", "ECE Project"],
                ["ECE Project", "USES", "Neo4j"],
            ],
        }
    )
    mock_llm.invoke.return_value = distill_json_str
    distill_input = DistillInput(raw_text=raw_text)

    # Act
    distilled_result = distiller_agent._run(distill_input)

    # Assert
    assert json.loads(distilled_result) == json.loads(distill_json_str)

    # --- 2. Archive Phase ---
    # Arrange
    archive_input = ArchiveInput(structured_summary=distilled_result)

    # Act
    archive_result = archivist_agent._run(archive_input)

    # Assert
    assert "Archive complete" in archive_result
    mock_db_manager.execute_query.assert_any_call(
        "MERGE (c:Concept {name: $name})", parameters={"name": "Coda"}
    )
    mock_db_manager.execute_query.assert_any_call(
        "MERGE (c:Concept {name: $name})", parameters={"name": "Neo4j"}
    )

    # --- 3. Extract Phase ---
    # Arrange
    question = "What does the ECE Project use?"
    generated_cypher = "MATCH (prj:Concept {name: 'ECE Project'})-[:USES]->(tech:Concept) RETURN tech.name"
    mock_llm.invoke.return_value = generated_cypher  # Set for the extractor call
    expected_db_output = [{"tech.name": "Neo4j"}]
    mock_db_manager.execute_query.return_value = expected_db_output
    extract_input = ExtractInput(question=question)

    # Act
    extract_result = extractor_agent._run(extract_input)

    # Assert
    assert json.loads(extract_result) == expected_db_output
    mock_db_manager.execute_query.assert_called_with(generated_cypher)
    print("\nIntegration test successful!")
