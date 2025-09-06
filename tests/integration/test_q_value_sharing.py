"""
Integration tests for Q-value sharing between QLearningGraphAgent and ArchivistAgent
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncio

from src.external_context_engine.memory_management.q_learning.q_learning_agent import QLearningGraphAgent
from src.external_context_engine.tools.archivist_agent import ArchivistAgent
from src.external_context_engine.utils.db_manager import Neo4jManager


class TestQValueSharingIntegration:
    """Test suite for integration between QLearningGraphAgent and ArchivistAgent"""
    
    @pytest.fixture
    def mock_neo4j_manager(self):
        """Create a mock Neo4jManager."""
        return MagicMock(spec=Neo4jManager)
    
    @pytest.fixture
    def q_learning_agent(self, mock_neo4j_manager):
        """Create a QLearningGraphAgent instance."""
        config = {
            "learning_rate": 0.1,
            "discount_factor": 0.9,
            "epsilon": 0.1,
            "max_episodes": 1000,
            "q_table_path": "./test_q_table.npy"
        }
        return QLearningGraphAgent(graph_manager=mock_neo4j_manager, config=config)
    
    @pytest.fixture
    def archivist_agent(self, mock_neo4j_manager):
        """Create an ArchivistAgent instance."""
        return ArchivistAgent(neo4j_manager=mock_neo4j_manager)
    
    @pytest.mark.asyncio
    async def test_q_value_persistence_and_retrieval(self, q_learning_agent, archivist_agent, mock_neo4j_manager):
        """Test that Q-values persisted by QLearningGraphAgent can be retrieved by ArchivistAgent."""
        # Set up a path for Q-learning
        path = ["NodeA", "NodeB", "NodeC"]
        reward = 0.8
        
        # Mock the graph manager responses for QLearningGraphAgent
        mock_neo4j_manager.execute_query.side_effect = [
            # First call for _update_q_value_in_graph (NodeA -> NodeB)
            [{}],
            # Second call for _update_q_value_in_graph (NodeB -> NodeC)
            [{}],
            # Call for retrieving paths with Q-values
            [
                {
                    "node_names": ["NodeA", "NodeB", "NodeC"],
                    "total_q_value": 0.5,
                    "path_length": 3
                }
            ]
        ]
        
        # Update Q-values in the QLearningGraphAgent
        await q_learning_agent.update_q_values(path, reward)
        
        # Verify that Q-values were persisted to the graph
        assert mock_neo4j_manager.execute_query.call_count >= 2
        
        # Reset mock call count for the next verification
        mock_neo4j_manager.execute_query.reset_mock()
        
        # Retrieve paths with Q-values using ArchivistAgent
        paths = await archivist_agent.retrieve_paths_with_qvalues("NodeA", "NodeC", max_hops=5)
        
        # Verify that the ArchivistAgent was able to retrieve paths with Q-values
        assert len(paths) == 1
        assert paths[0]["node_names"] == ["NodeA", "NodeB", "NodeC"]
        assert "total_q_value" in paths[0]
        assert "path_length" in paths[0]
        
        # Verify that the correct Cypher query was executed
        mock_neo4j_manager.execute_query.assert_called_once()
        call_args = mock_neo4j_manager.execute_query.call_args
        assert "MATCH path = (start {name: $start_node})-[:TRANSITION*..$max_hops]->(end {name: $end_node})" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_optimal_path_retrieval(self, q_learning_agent, archivist_agent, mock_neo4j_manager):
        """Test that ArchivistAgent can retrieve the optimal path based on Q-values."""
        # Mock the graph manager response for optimal path retrieval
        mock_neo4j_manager.execute_query.return_value = [
            {
                "node_names": ["NodeA", "NodeB", "NodeC"],
                "total_q_value": 1.5,
                "path_length": 3
            }
        ]
        
        # Get the optimal path using ArchivistAgent
        optimal_path = await archivist_agent.get_optimal_path("NodeA", "NodeC", max_hops=5)
        
        # Verify the result
        assert optimal_path is not None
        assert optimal_path["node_names"] == ["NodeA", "NodeB", "NodeC"]
        assert optimal_path["total_q_value"] == 1.5
        assert optimal_path["path_length"] == 3
        
        # Verify that the correct Cypher query was executed
        mock_neo4j_manager.execute_query.assert_called_once()
        call_args = mock_neo4j_manager.execute_query.call_args
        assert "MATCH path = (start {name: $start_node})-[:TRANSITION*..$max_hops]->(end {name: $end_node})" in call_args[0][0]
        assert "ORDER BY total_q_value DESC" in call_args[0][0]
        assert "LIMIT 1" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_q_table_synchronization(self, q_learning_agent, mock_neo4j_manager):
        """Test that Q-table synchronization works correctly."""
        # Set up some Q-values in the Q-table
        q_learning_agent.q_table.update("NodeA", "NodeA→NodeB", 0.5)
        q_learning_agent.q_table.update("NodeB", "NodeB→NodeC", 0.8)
        
        # Mock the graph manager responses
        mock_neo4j_manager.execute_query.return_value = [{}]
        
        # Synchronize Q-values with the graph
        await q_learning_agent.sync_q_values_to_graph()
        
        # Verify that the graph manager was called for each Q-value
        assert mock_neo4j_manager.execute_query.call_count == 2
        
        # Verify the parameters for each call
        calls = mock_neo4j_manager.execute_query.call_args_list
        first_call_args = calls[0][0][1]
        second_call_args = calls[1][0][1]
        
        # Check that the correct nodes and Q-values were passed
        assert first_call_args["from_node"] in ["NodeA", "NodeB"]
        assert first_call_args["to_node"] in ["NodeB", "NodeC"]
        assert first_call_args["q_value"] in [0.5, 0.8]
        
        assert second_call_args["from_node"] in ["NodeA", "NodeB"]
        assert second_call_args["to_node"] in ["NodeB", "NodeC"]
        assert second_call_args["q_value"] in [0.5, 0.8]
    
    @pytest.mark.asyncio
    async def test_initialize_q_table_from_graph(self, q_learning_agent, mock_neo4j_manager):
        """Test initializing Q-table from graph data."""
        # Mock the graph manager response with existing Q-values
        mock_neo4j_manager.execute_query.return_value = [
            {"from_node": "NodeA", "to_node": "NodeB", "q_value": 0.5},
            {"from_node": "NodeB", "to_node": "NodeC", "q_value": 0.8}
        ]
        
        # Initialize Q-table from graph
        await q_learning_agent._initialize_q_table_from_graph()
        
        # Verify that Q-values were added to the Q-table
        assert q_learning_agent.q_table.get_q_value("NodeA", "NodeA→NodeB") == 0.5
        assert q_learning_agent.q_table.get_q_value("NodeB", "NodeB→NodeC") == 0.8
        
        # Verify that the correct Cypher query was executed
        mock_neo4j_manager.execute_query.assert_called_once()
        call_args = mock_neo4j_manager.execute_query.call_args
        assert "MATCH (from)-[r:TRANSITION]->(to)" in call_args[0][0]
        assert "WHERE exists(r.q_value)" in call_args[0][0]


if __name__ == "__main__":
    pytest.main([__file__])