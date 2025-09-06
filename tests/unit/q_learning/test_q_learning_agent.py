"""
Unit tests for the QLearningGraphAgent
"""
import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, AsyncMock, patch
from src.external_context_engine.memory_management.q_learning.q_learning_agent import (
    QLearningGraphAgent, 
    QTable, 
    GraphState, 
    Action
)
from src.external_context_engine.memory_management.models.memory_path import MemoryPath


class TestQTable:
    """Test suite for the QTable class"""
    
    def test_init(self):
        """Test QTable initialization"""
        q_table = QTable()
        assert q_table.persist_path is None
        assert len(q_table.q_values) == 0
        
        q_table = QTable("./test_q_table.npy")
        assert q_table.persist_path == "./test_q_table.npy"
    
    def test_get_q_value(self):
        """Test getting Q-values"""
        q_table = QTable()
        # Test default value for non-existent state-action pair
        assert q_table.get_q_value("state1", "action1") == 0.0
        
        # Test setting and getting a Q-value
        q_table.update("state1", "action1", 1.5)
        assert q_table.get_q_value("state1", "action1") == 1.5
    
    def test_get_max_q_value(self):
        """Test getting maximum Q-value for a state"""
        q_table = QTable()
        # Test default value for non-existent state
        assert q_table.get_max_q_value("state1") == 0.0
        
        # Test with existing Q-values
        q_table.update("state1", "action1", 1.5)
        q_table.update("state1", "action2", 2.0)
        q_table.update("state1", "action3", 1.0)
        assert q_table.get_max_q_value("state1") == 2.0
    
    def test_update(self):
        """Test updating Q-values"""
        q_table = QTable()
        q_table.update("state1", "action1", 1.5)
        assert q_table.get_q_value("state1", "action1") == 1.5
        
        # Test updating existing Q-value
        q_table.update("state1", "action1", 2.5)
        assert q_table.get_q_value("state1", "action1") == 2.5


class TestQLearningGraphAgent:
    """Test suite for the QLearningGraphAgent class"""
    
    @pytest.fixture
    def mock_graph_manager(self):
        """Create a mock graph manager"""
        return Mock()
    
    @pytest.fixture
    def agent(self, mock_graph_manager):
        """Create a QLearningGraphAgent instance"""
        config = {
            "learning_rate": 0.1,
            "discount_factor": 0.9,
            "epsilon": 0.1,
            "max_episodes": 1000,
            "q_table_path": "./test_q_table.npy"
        }
        return QLearningGraphAgent(mock_graph_manager, config)
    
    def test_init(self, agent):
        """Test QLearningGraphAgent initialization"""
        assert agent.learning_rate == 0.1
        assert agent.discount_factor == 0.9
        assert agent.epsilon == 0.1
        assert agent.max_episodes == 1000
        assert agent.q_table.persist_path == "./test_q_table.npy"
        assert agent.episode_count == 0
        assert len(agent.total_rewards) == 0
        assert len(agent.path_cache) == 0
    
    @pytest.mark.asyncio
    async def test_initialize(self, agent):
        """Test QLearningGraphAgent initialization"""
        # Mock the Q-table load method
        with patch.object(agent.q_table, 'load', new_callable=AsyncMock) as mock_load:
            await agent.initialize()
            mock_load.assert_called_once()
    
    def test_get_state_key(self, agent):
        """Test state key generation"""
        # Test with string
        assert agent._get_state_key("node1") == "node1"
        
        # Test with dict
        assert agent._get_state_key({"name": "node1"}) == "node1"
        assert agent._get_state_key({"id": "123"}) == "123"
        assert agent._get_state_key({"other": "value"}) == "{'other': 'value'}"
    
    def test_get_action_key(self, agent):
        """Test action key generation"""
        # Test with dict
        action = {"from": "node1", "to_node": "node2"}
        assert agent._get_action_key(action) == "node1→node2"
        
        # Test with dict having 'to' instead of 'to_node'
        action = {"from": "node1", "to": "node2"}
        assert agent._get_action_key(action) == "node1→node2"
        
        # Test with non-dict
        assert agent._get_action_key("action1") == "action1"
    
    def test_rank_paths(self, agent):
        """Test path ranking by Q-values"""
        # Create test paths with different scores
        path1 = MemoryPath(nodes=["A", "B"], score=0.5)
        path2 = MemoryPath(nodes=["A", "C"], score=0.8)
        path3 = MemoryPath(nodes=["A", "D"], score=0.3)
        
        paths = [path1, path2, path3]
        ranked_paths = agent._rank_paths(paths)
        
        # Check that paths are ranked by score (descending)
        assert ranked_paths[0].score == 0.8
        assert ranked_paths[1].score == 0.5
        assert ranked_paths[2].score == 0.3
    
    def test_select_best_action(self, agent):
        """Test selection of best action based on Q-values"""
        # Set up Q-values
        agent.q_table.update("node1", "node1→node2", 0.5)
        agent.q_table.update("node1", "node1→node3", 0.8)
        agent.q_table.update("node1", "node1→node4", 0.3)
        
        # Test actions
        actions = [
            {"from": "node1", "to_node": "node2"},
            {"from": "node1", "to_node": "node3"},
            {"from": "node1", "to_node": "node4"}
        ]
        
        best_action = agent._select_best_action("node1", actions)
        assert best_action["to_node"] == "node3"
    
    @pytest.mark.asyncio
    async def test_get_neighbors(self, agent, mock_graph_manager):
        """Test getting neighboring nodes"""
        # Mock the graph manager response
        mock_graph_manager.execute_query.return_value = [
            {"to_node": "node2", "type": "RELATES_TO", "strength": 0.8},
            {"to_node": "node3", "type": "RELATED_TO", "strength": 0.6}
        ]
        
        neighbors = await agent._get_neighbors("node1")
        assert len(neighbors) == 2
        assert neighbors[0]["to_node"] == "node2"
        assert neighbors[1]["to_node"] == "node3"
        mock_graph_manager.execute_query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_shortest_path(self, agent, mock_graph_manager):
        """Test finding shortest path between nodes"""
        # Mock the graph manager response
        mock_graph_manager.execute_query.return_value = [
            {"path": ["node1", "node2", "node3"]}
        ]
        
        path = await agent._find_shortest_path("node1", "node3")
        assert path == ["node1", "node2", "node3"]
        mock_graph_manager.execute_query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_q_values(self, agent):
        """Test updating Q-values based on a path"""
        # Create a test path
        path = ["node1", "node2", "node3"]
        
        # Mock the Q-table methods
        with patch.object(agent.q_table, 'get_q_value', return_value=0.5) as mock_get, \
             patch.object(agent.q_table, 'get_max_q_value', return_value=0.8) as mock_get_max, \
             patch.object(agent.q_table, 'update') as mock_update, \
             patch.object(agent, '_update_q_value_in_graph', new_callable=AsyncMock) as mock_update_graph:
            
            await agent.update_q_values(path, 1.0)
            
            # Check that Q-values were updated for each state-action pair
            assert mock_get.call_count == 2  # Two transitions in the path
            assert mock_get_max.call_count == 2
            assert mock_update.call_count == 2
            assert mock_update_graph.call_count == 2  # Two transitions in the path
            
            # Check episode tracking
            assert agent.episode_count == 1
            assert len(agent.total_rewards) == 1
            assert agent.total_rewards[0] == 1.0
    
    @pytest.mark.asyncio
    async def test_update_q_value_in_graph(self, agent, mock_graph_manager):
        """Test updating Q-value in the graph"""
        # Mock the graph manager response
        mock_graph_manager.execute_query.return_value = [{}]
        
        await agent._update_q_value_in_graph("node1", "node2", 0.8)
        
        # Check that the graph manager was called with the correct query and parameters
        mock_graph_manager.execute_query.assert_called_once()
        call_args = mock_graph_manager.execute_query.call_args
        assert "MATCH (from {name: $from_node}), (to {name: $to_node})" in call_args[0][0]
        assert call_args[0][1]["from_node"] == "node1"
        assert call_args[0][1]["to_node"] == "node2"
        assert call_args[0][1]["q_value"] == 0.8
    
    @pytest.mark.asyncio
    async def test_sync_q_values_to_graph(self, agent, mock_graph_manager):
        """Test synchronizing Q-values with the graph"""
        # Set up some Q-values in the Q-table
        agent.q_table.update("node1", "node1\u2192node2", 0.5)
        agent.q_table.update("node2", "node2\u2192node3", 0.8)
        
        # Mock the graph manager response
        mock_graph_manager.execute_query.return_value = [{}]
        
        await agent.sync_q_values_to_graph()
        
        # Check that the graph manager was called for each Q-value
        assert mock_graph_manager.execute_query.call_count == 2
    
    @pytest.mark.asyncio
    async def test_initialize_q_table_from_graph(self, agent, mock_graph_manager):
        """Test initializing Q-table from the graph"""
        # Mock the graph manager response
        mock_graph_manager.execute_query.return_value = [
            {"from_node": "node1", "to_node": "node2", "q_value": 0.5},
            {"from_node": "node2", "to_node": "node3", "q_value": 0.8}
        ]
        
        await agent._initialize_q_table_from_graph()
        
        # Check that Q-values were added to the Q-table
        assert agent.q_table.get_q_value("node1", "node1\u2192node2") == 0.5
        assert agent.q_table.get_q_value("node2", "node2\u2192node3") == 0.8
    
    @pytest.mark.asyncio
    async def test_select_best_action_with_graph_q_values(self, agent):
        """Test selection of best action using Q-values from graph"""
        # Set up Q-values in memory
        agent.q_table.update("node1", "node1\u2192node2", 0.5)
        
        # Test actions with one having a Q-value from graph
        actions = [
            {"from": "node1", "to_node": "node2"},  # Has Q-value in memory
            {"from": "node1", "to_node": "node3", "q_value": 0.8}  # Has Q-value from graph
        ]
        
        best_action = agent._select_best_action("node1", actions)
        assert best_action["to_node"] == "node3"  # Should select action with higher Q-value
    
    def test_get_convergence_metrics(self, agent):
        """Test getting convergence metrics"""
        # Test with no rewards
        metrics = agent.get_convergence_metrics()
        assert metrics["converged"] == False
        assert metrics["episodes"] == 0
        
        # Test with some rewards
        agent.episode_count = 5
        agent.total_rewards = [0.5, 0.6, 0.7, 0.8, 0.9]
        metrics = agent.get_convergence_metrics()
        assert metrics["episodes"] == 5
        assert metrics["average_reward"] == 0.7
        assert metrics["epsilon"] == 0.1
        assert "q_table_size" in metrics


if __name__ == "__main__":
    pytest.main([__file__])