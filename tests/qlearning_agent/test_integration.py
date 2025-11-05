"""
Integration tests for the QLearningAgent's Neo4j integration
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import numpy as np
from ece.agents.tier3.qlearning.qlearning_agent import QLearningGraphAgent
from ece.agents.tier3.qlearning.neo4j_manager import Neo4jManager


@pytest.fixture
def mock_graph_manager():
    """Create a mock graph manager for testing"""
    return Mock()


@pytest.fixture
def q_learning_agent(mock_graph_manager):
    """Create a QLearningGraphAgent instance for testing"""
    config = {
        "learning_rate": 0.1,
        "discount_factor": 0.9,
        "epsilon": 0.1,
        "training_interval": 300,
    }
    agent = QLearningGraphAgent(mock_graph_manager, config)
    return agent


@pytest.mark.asyncio
async def test_sync_q_values_to_graph(q_learning_agent, mock_graph_manager):
    """Test synchronizing Q-values to Neo4j graph"""
    # Populate Q-table with some values
    q_learning_agent.q_table = {
        "node1": {"node2:RELATED_TO": 0.5, "node3:CONNECTED_TO": 0.8},
        "node2": {"node4:LINKED_TO": 0.3},
    }

    # Mock the graph manager's sync method
    mock_graph_manager.sync_q_values_to_graph = Mock()

    await q_learning_agent.sync_q_values_to_graph()

    # Verify the graph manager's method was called with the Q-table
    mock_graph_manager.sync_q_values_to_graph.assert_called_once_with(
        q_learning_agent.q_table
    )


@pytest.mark.asyncio
async def test_query_graph_structure(q_learning_agent, mock_graph_manager):
    """Test querying graph structure"""
    # Mock graph response
    mock_neighbors = [
        {
            "from_node": "node1",
            "to_node": "node2",
            "relationship_type": "RELATED_TO",
            "relationship_properties": {"q_value": 0.5},
            "neighbor_properties": {"id": "node2", "name": "Node 2"},
        },
        {
            "from_node": "node1",
            "to_node": "node3",
            "relationship_type": "CONNECTED_TO",
            "relationship_properties": {"q_value": 0.7},
            "neighbor_properties": {"id": "node3", "name": "Node 3"},
        },
    ]
    mock_graph_manager.get_neighbors.return_value = mock_neighbors

    actions = await q_learning_agent._query_graph_structure("node1")

    assert len(actions) == 2
    assert actions[0].from_node == "node1"
    assert actions[0].to_node == "node2"
    assert actions[0].relationship_type == "RELATED_TO"
    assert actions[1].from_node == "node1"
    assert actions[1].to_node == "node3"
    assert actions[1].relationship_type == "CONNECTED_TO"

    # Verify the query was called correctly
    mock_graph_manager.get_neighbors.assert_called_once_with("node1")


@pytest.mark.asyncio
async def test_continuous_training_loop(q_learning_agent, mock_graph_manager):
    """Test continuous training loop"""
    # Mock the methods called in the training loop
    with (
        patch.object(q_learning_agent, "_get_random_node") as mock_get_node,
        patch.object(
            q_learning_agent, "_explore_from_node", new_callable=AsyncMock
        ) as mock_explore,
        patch.object(
            q_learning_agent, "sync_q_values_to_graph", new_callable=AsyncMock
        ) as mock_sync,
    ):
        # Mock getting a random node
        mock_get_node.return_value = "node1"

        # Test one iteration of the training loop
        await q_learning_agent._perform_continuous_training()

        # Verify methods were called
        mock_get_node.assert_called_once()
        mock_explore.assert_called_once_with("node1")
        mock_sync.assert_called_once()


@pytest.mark.asyncio
async def test_explore_from_node(q_learning_agent, mock_graph_manager):
    """Test exploring from a node"""
    # Mock the query graph structure method
    with patch.object(
        q_learning_agent, "_query_graph_structure", new_callable=AsyncMock
    ) as mock_query:
        # Mock returning some actions
        mock_actions = [
            Mock(from_node="node1", to_node="node2", relationship_type="RELATED_TO"),
            Mock(from_node="node1", to_node="node3", relationship_type="CONNECTED_TO"),
        ]
        mock_query.return_value = mock_actions

        # Mock the update_q_values method
        with patch.object(
            q_learning_agent, "update_q_values", new_callable=AsyncMock
        ) as mock_update:
            await q_learning_agent._explore_from_node("node1", max_steps=2)

            # Verify methods were called
            mock_query.assert_called_once_with("node1")
            mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_q_learning_pathfinding(q_learning_agent, mock_graph_manager):
    """Test Q-learning pathfinding"""
    # Mock the query graph structure method
    with patch.object(
        q_learning_agent, "_query_graph_structure", new_callable=AsyncMock
    ) as mock_query:
        # Mock returning some actions
        mock_actions = [
            Mock(from_node="start", to_node="middle", relationship_type="RELATED_TO"),
            Mock(from_node="middle", to_node="end", relationship_type="CONNECTED_TO"),
        ]

        # Return different actions for different nodes
        mock_query.side_effect = [
            [mock_actions[0]],  # First call for "start"
            [mock_actions[1]],  # Second call for "middle"
            [],  # Third call for "end" (no neighbors)
        ]

        # Set some Q-values to influence path selection
        q_learning_agent._set_q_value("start", "middle:RELATED_TO", 0.8)
        q_learning_agent._set_q_value("middle", "end:CONNECTED_TO", 0.9)

        # Find path with exploitation (low epsilon)
        q_learning_agent.epsilon = 0.0  # Always exploit
        path = await q_learning_agent._q_learning_pathfinding(
            "start", "end", max_steps=10
        )

        # Verify the path
        assert len(path.nodes) == 3
        assert path.nodes[0] == "start"
        assert path.nodes[1] == "middle"
        assert path.nodes[2] == "end"
        assert path.length == 2
        assert path.score == 1.0  # Perfect score for reaching target


def test_neo4j_manager_initialization():
    """Test Neo4jManager initialization"""
    manager = Neo4jManager("bolt://localhost:7688", "neo4j", "password")
    assert manager.uri == "bolt://localhost:7688"
    assert manager.user == "neo4j"
    assert manager.password == "password"
    assert manager._driver is None


def test_calculate_path_score(q_learning_agent):
    """Test calculating path score"""
    # Test perfect score for reaching target
    path = Mock()
    path.nodes = ["start", "target"]
    score = q_learning_agent._calculate_path_score(path, "target")
    assert score == 1.0

    # Test partial score for non-target path
    path.nodes = ["start", "middle"]
    path.length = 1
    score = q_learning_agent._calculate_path_score(path, "target")
    assert 0.0 <= score <= 0.5  # Should be between 0 and 0.5 for non-target paths
