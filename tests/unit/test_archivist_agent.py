"""
Unit tests for the ArchivistAgent
"""

import pytest
from unittest.mock import MagicMock
from src.external_context_engine.tools.archivist_agent import ArchivistAgent, Entity, Relationship, Query
from src.external_context_engine.utils.db_manager import Neo4jManager


@pytest.fixture
def mock_neo4j_manager():
    """Create a mock Neo4jManager."""
    return MagicMock(spec=Neo4jManager)


@pytest.fixture
def archivist_agent(mock_neo4j_manager):
    """Create an ArchivistAgent instance with a mock Neo4jManager."""
    return ArchivistAgent(neo4j_manager=mock_neo4j_manager)


def test_init(archivist_agent, mock_neo4j_manager):
    """Test initialization of the ArchivistAgent."""
    assert isinstance(archivist_agent, ArchivistAgent)
    assert archivist_agent.graph_db == mock_neo4j_manager


@pytest.mark.asyncio
async def test_store_entities(archivist_agent, mock_neo4j_manager):
    """Test storing entities in the knowledge graph."""
    # Mock the create_node method
    mock_neo4j_manager.create_node.return_value = {"n": {"id": "1", "name": "Test Entity"}}
    
    # Create test entities
    entities = [
        Entity(id="1", type="Person", properties={"name": "John Doe", "age": 30}),
        Entity(id="2", type="Organization", properties={"name": "ACME Corp", "industry": "Technology"})
    ]
    
    # Call the store method
    result = await archivist_agent.store(entities)
    
    # Verify the result
    assert result["success"] is True
    assert result["stored_entities"] == 2
    assert result["stored_relationships"] == 0
    
    # Verify that create_node was called twice
    assert mock_neo4j_manager.create_node.call_count == 2


@pytest.mark.asyncio
async def test_store_relationships(archivist_agent, mock_neo4j_manager):
    """Test storing relationships in the knowledge graph."""
    # Mock the create_relationship_by_ids method
    mock_neo4j_manager.create_relationship_by_ids.return_value = {"r": {"id": "1", "type": "WORKS_FOR"}}
    
    # Create test relationship
    relationships = [
        Relationship(
            id="1",
            type="WORKS_FOR",
            start_entity_id="1",
            end_entity_id="2",
            properties={"since": "2020"}
        )
    ]
    
    # Call the store method
    result = await archivist_agent.store(relationships)
    
    # Verify the result
    assert result["success"] is True
    assert result["stored_entities"] == 0
    assert result["stored_relationships"] == 1
    
    # Verify that create_relationship_by_ids was called once
    mock_neo4j_manager.create_relationship_by_ids.assert_called_once_with(
        start_node_id="1",
        end_node_id="2",
        relationship_type="WORKS_FOR",
        properties={"since": "2020"}
    )


@pytest.mark.asyncio
async def test_retrieve(archivist_agent, mock_neo4j_manager):
    """Test retrieving information from the knowledge graph."""
    # Mock the execute_query method
    mock_results = [{"name": "John Doe", "age": 30}, {"name": "Jane Smith", "age": 25}]
    mock_neo4j_manager.execute_query.return_value = mock_results
    
    # Create test query
    query = Query(
        cypher="MATCH (p:Person) RETURN p.name, p.age",
        parameters={}
    )
    
    # Call the retrieve method
    result = await archivist_agent.retrieve(query)
    
    # Verify the result
    assert result == mock_results
    mock_neo4j_manager.execute_query.assert_called_once_with(
        query=query.cypher,
        parameters=query.parameters
    )


@pytest.mark.asyncio
async def test_update_entity(archivist_agent, mock_neo4j_manager):
    """Test updating an entity in the knowledge graph."""
    # Mock the find_nodes_by_property method
    mock_neo4j_manager.find_nodes_by_property.return_value = [{"n": MagicMock(id=1)}]
    
    # Create test entity
    entity = Entity(id="1", type="Person", properties={"name": "John Doe", "age": 31})
    
    # Call the update method
    result = await archivist_agent.update(entity)
    
    # Verify the result
    assert result["success"] is True
    assert result["updated"] is True
    assert result["id"] == "1"


@pytest.mark.asyncio
async def test_delete_entity(archivist_agent, mock_neo4j_manager):
    """Test deleting an entity from the knowledge graph."""
    # Mock the execute_query method
    mock_neo4j_manager.execute_query.return_value = []
    
    # Call the delete method
    result = await archivist_agent.delete("1", "entity")
    
    # Verify the result
    assert result["success"] is True
    assert result["deleted"] is True
    assert result["id"] == "1"
    assert result["type"] == "entity"
    
    # Verify that execute_query was called with the correct query
    mock_neo4j_manager.execute_query.assert_called_once()


@pytest.mark.asyncio
async def test_delete_relationship(archivist_agent, mock_neo4j_manager):
    """Test deleting a relationship from the knowledge graph."""
    # Mock the execute_query method
    mock_neo4j_manager.execute_query.return_value = []
    
    # Call the delete method
    result = await archivist_agent.delete("1", "relationship")
    
    # Verify the result
    assert result["success"] is True
    assert result["deleted"] is True
    assert result["id"] == "1"
    assert result["type"] == "relationship"
    
    # Verify that execute_query was called with the correct query
    mock_neo4j_manager.execute_query.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_paths_with_qvalues(archivist_agent, mock_neo4j_manager):
    """Test retrieving paths with Q-values from the knowledge graph."""
    # Mock the execute_query method
    mock_results = [
        {
            "node_names": ["NodeA", "NodeB", "NodeC"],
            "total_q_value": 1.5,
            "path_length": 3
        },
        {
            "node_names": ["NodeA", "NodeD", "NodeC"],
            "total_q_value": 1.2,
            "path_length": 3
        }
    ]
    mock_neo4j_manager.execute_query.return_value = mock_results
    
    # Call the retrieve_paths_with_qvalues method
    result = await archivist_agent.retrieve_paths_with_qvalues("NodeA", "NodeC", max_hops=5)
    
    # Verify the result
    assert result == mock_results
    mock_neo4j_manager.execute_query.assert_called_once()
    
    # Verify the query parameters
    call_args = mock_neo4j_manager.execute_query.call_args
    assert "MATCH path = (start {name: $start_node})-[:TRANSITION*..$max_hops]->(end {name: $end_node})" in call_args[0][0]
    assert call_args[0][1]["start_node"] == "NodeA"
    assert call_args[0][1]["end_node"] == "NodeC"
    assert call_args[0][1]["max_hops"] == 5


@pytest.mark.asyncio
async def test_get_optimal_path(archivist_agent, mock_neo4j_manager):
    """Test getting the optimal path based on Q-values."""
    # Mock the execute_query method
    mock_results = [
        {
            "node_names": ["NodeA", "NodeB", "NodeC"],
            "total_q_value": 1.5,
            "path_length": 3
        }
    ]
    mock_neo4j_manager.execute_query.return_value = mock_results
    
    # Call the get_optimal_path method
    result = await archivist_agent.get_optimal_path("NodeA", "NodeC", max_hops=5)
    
    # Verify the result
    assert result == mock_results[0]
    mock_neo4j_manager.execute_query.assert_called_once()
    
    # Verify the query parameters
    call_args = mock_neo4j_manager.execute_query.call_args
    assert "MATCH path = (start {name: $start_node})-[:TRANSITION*..$max_hops]->(end {name: $end_node})" in call_args[0][0]
    assert call_args[0][1]["start_node"] == "NodeA"
    assert call_args[0][1]["end_node"] == "NodeC"
    assert call_args[0][1]["max_hops"] == 5