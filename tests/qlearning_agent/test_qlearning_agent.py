"""
Unit tests for the QLearningAgent's pathfinding logic
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import numpy as np
from ece.agents.tier3.qlearning.qlearning_agent import (
    QLearningGraphAgent, 
    MemoryPath
)


@pytest.fixture
def mock_graph_manager():
    """Create a mock graph manager for testing"""
    mock_graph_manager.find_nodes_by_keywords = AsyncMock(return_value=[{"id": "start", "name": "start"}, {"id": "end", "name": "end"}])
    return mock_graph_manager


@pytest.fixture
def q_learning_agent(mock_graph_manager):
    """Create a QLearningGraphAgent instance for testing"""
    config = {
        "learning_rate": 0.1,
        "discount_factor": 0.9,
        "epsilon": 0.1,
        "training_interval": 300
    }
    agent = QLearningGraphAgent(mock_graph_manager, config)
    return agent


def test_initialization(q_learning_agent, mock_graph_manager):
    """Test agent initialization"""
    assert q_learning_agent.graph_manager == mock_graph_manager
    assert q_learning_agent.learning_rate == 0.1
    assert q_learning_agent.discount_factor == 0.9
    assert q_learning_agent.epsilon == 0.1
    assert q_learning_agent.q_table == {}
    assert q_learning_agent.is_training == False


@pytest.mark.asyncio
async def test_find_optimal_path(q_learning_agent):
    """Test finding optimal path"""
    # Mock the pathfinding method
    with patch.object(q_learning_agent, '_q_learning_pathfinding', new_callable=AsyncMock) as mock_pathfinding:
        mock_path = MemoryPath(
            nodes=["start", "end"], 
            relationships=[{"start_node": "start", "end_node": "end", "type": "RELATED_TO"}], 
            score=0.8, 
            length=1
        )
        mock_pathfinding.return_value = mock_path
        
        paths = await q_learning_agent.find_optimal_path(["start", "end"])
        
        assert len(paths) == 1
        assert paths[0].score == 0.8
        mock_pathfinding.assert_called_once_with("start", "end")


@pytest.mark.asyncio
async def test_update_q_values(q_learning_agent):
    """Test updating Q-values"""
    # Create a path
    path = MemoryPath(
        nodes=["node1", "node2", "node3"],
        relationships=[
            {"start_node": "node1", "end_node": "node2", "type": "RELATED_TO"},
            {"start_node": "node2", "end_node": "node3", "type": "CONNECTED_TO"}
        ],
        score=0.8,
        length=2
    )
    
    # Test updating Q-values
    await q_learning_agent.update_q_values(path, 1.0)
    
    # Verify Q-table was updated
    assert "node1" in q_learning_agent.q_table
    assert "node2:RELATED_TO" in q_learning_agent.q_table["node1"]
    assert q_learning_agent.q_table["node1"]["node2:RELATED_TO"] != 0.0


@pytest.mark.asyncio
async def test_train(q_learning_agent):
    """Test training with historical data"""
    # Mock the pathfinding method
    with patch.object(q_learning_agent, '_q_learning_pathfinding', new_callable=AsyncMock) as mock_pathfinding:
        mock_path = MemoryPath(
            nodes=["start", "end"], 
            relationships=[{"start_node": "start", "end_node": "end", "type": "RELATED_TO"}], 
            score=0.8, 
            length=1
        )
        mock_pathfinding.return_value = mock_path
        
        # Training data
        training_data = [
            ("start", "end", 0.8),
            ("node1", "node2", 0.6)
        ]
        
        await q_learning_agent.train(training_data)
        
        # Verify training flag was set and unset
        assert q_learning_agent.is_training == False
        # Verify pathfinding was called for each training item
        assert mock_pathfinding.call_count == 2


@pytest.mark.asyncio
async def test_start_continuous_training(q_learning_agent):
    """Test starting continuous training"""
    with patch.object(q_learning_agent, '_continuous_training_loop', new_callable=AsyncMock) as mock_loop:
        mock_loop.return_value = None
        
        # Start continuous training
        await q_learning_agent.start_continuous_training()
        
        # Verify training task was created
        assert q_learning_agent.training_task is not None
        assert not q_learning_agent.training_task.done()


@pytest.mark.asyncio
async def test_stop_continuous_training(q_learning_agent):
    """Test stopping continuous training"""
    with patch.object(q_learning_agent, '_continuous_training_loop', new_callable=AsyncMock) as mock_loop:
        mock_loop.return_value = None
        
        # Start continuous training
        await q_learning_agent.start_continuous_training()
        
        # Stop continuous training
        await q_learning_agent.stop_continuous_training()
        
        # Verify training task was cancelled
        assert q_learning_agent.training_task is None or q_learning_agent.training_task.cancelled()


def test_get_convergence_metrics(q_learning_agent):
    """Test getting convergence metrics"""
    # Test with empty Q-table
    metrics = q_learning_agent.get_convergence_metrics()
    assert metrics["q_table_size"] == 0
    assert metrics["total_q_values"] == 0
    assert metrics["average_q_value"] == 0.0
    
    # Add some Q-values
    q_learning_agent.q_table = {
        "node1": {
            "node2:RELATED_TO": 0.5,
            "node3:CONNECTED_TO": 0.8
        },
        "node2": {
            "node4:LINKED_TO": 0.3
        }
    }
    
    metrics = q_learning_agent.get_convergence_metrics()
    assert metrics["q_table_size"] == 2
    assert metrics["total_q_values"] == 3
    assert metrics["average_q_value"] == (0.5 + 0.8 + 0.3) / 3
    assert metrics["max_q_value"] == 0.8
    assert metrics["min_q_value"] == 0.3


def test_get_q_value(q_learning_agent):
    """Test getting Q-value from Q-table"""
    # Test default value for missing state-action pair
    assert q_learning_agent._get_q_value("state1", "action1") == 0.0
    
    # Set a Q-value
    q_learning_agent._set_q_value("state1", "action1", 0.5)
    
    # Test getting the set value
    assert q_learning_agent._get_q_value("state1", "action1") == 0.5


def test_set_q_value(q_learning_agent):
    """Test setting Q-value in Q-table"""
    # Set a Q-value
    q_learning_agent._set_q_value("state1", "action1", 0.5)
    
    # Test getting the set value
    assert q_learning_agent._get_q_value("state1", "action1") == 0.5
    
    # Update existing value
    q_learning_agent._set_q_value("state1", "action1", 0.7)
    assert q_learning_agent._get_q_value("state1", "action1") == 0.7


def test_get_max_q_value(q_learning_agent):
    """Test getting maximum Q-value for a state"""
    # Test default value for missing state
    assert q_learning_agent._get_max_q_value("state1") == 0.0
    
    # Set Q-values for a state
    q_learning_agent._set_q_value("state1", "action1", 0.5)
    q_learning_agent._set_q_value("state1", "action2", 0.8)
    q_learning_agent._set_q_value("state1", "action3", 0.3)
    
    # Test getting maximum value
    assert q_learning_agent._get_max_q_value("state1") == 0.8


@pytest.mark.asyncio
async def test_refine_relationships(q_learning_agent):
    """Test refining relationships."""
    # Create a mock path
    path = MemoryPath(
        nodes=["nodeA", "nodeB"],
        relationships=[{"start_node": "nodeA", "end_node": "nodeB", "type": "RELATES_TO"}],
        score=0.5,
        length=1
    )
    
    # Mock the update_q_values method
    with patch.object(q_learning_agent, 'update_q_values', new_callable=AsyncMock) as mock_update_q_values:
        await q_learning_agent.refine_relationships(path, reward=1.0)
        mock_update_q_values.assert_called_once_with(path, 1.0)