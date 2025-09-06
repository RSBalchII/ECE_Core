"""
Integration tests for the QLearningGraphAgent API endpoints
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.external_context_engine.main import app


class TestQLearningAPI:
    """Test suite for the QLearningGraphAgent API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create a test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_q_learning_agent(self):
        """Create a mock Q-learning agent"""
        with patch('src.external_context_engine.main.q_learning_agent') as mock_agent:
            # Configure the mock agent
            mock_agent.find_paths = AsyncMock()
            mock_agent.update_q_values = AsyncMock()
            mock_agent.train = AsyncMock()
            mock_agent.get_convergence_metrics = Mock()
            yield mock_agent
    
    def test_find_paths_endpoint(self, client, mock_q_learning_agent):
        """Test the find_paths endpoint"""
        # Mock the agent response
        from src.external_context_engine.memory_management.models.memory_path import MemoryPath
        mock_paths = [
            MemoryPath(nodes=["A", "B", "C"], score=0.8),
            MemoryPath(nodes=["A", "D", "C"], score=0.6)
        ]
        mock_q_learning_agent.find_paths.return_value = mock_paths
        
        # Test request data
        request_data = {
            "start_nodes": [{"name": "A"}],
            "end_nodes": [{"name": "C"}],
            "max_hops": 5
        }
        
        # Make the request
        response = client.post("/q_learning/find_paths", json=request_data)
        
        # Check the response
        assert response.status_code == 200
        assert len(response.json()) == 2
        mock_q_learning_agent.find_paths.assert_called_once()
    
    def test_update_q_values_endpoint(self, client, mock_q_learning_agent):
        """Test the update_q_values endpoint"""
        # Mock the agent response
        mock_q_learning_agent.update_q_values.return_value = None
        
        # Test request data
        request_data = {
            "path": ["A", "B", "C"],
            "reward": 0.8
        }
        
        # Make the request
        response = client.post("/q_learning/update_q_values", json=request_data)
        
        # Check the response
        assert response.status_code == 200
        assert response.json() == {"status": "success", "message": "Q-values updated"}
        mock_q_learning_agent.update_q_values.assert_called_once()
    
    def test_train_endpoint(self, client, mock_q_learning_agent):
        """Test the train endpoint"""
        # Mock the agent response
        mock_q_learning_agent.train.return_value = None
        
        # Test request data
        request_data = {
            "training_data": [
                ["A", "C", 0.8],
                ["B", "D", 0.6]
            ]
        }
        
        # Make the request
        response = client.post("/q_learning/train", json=request_data)
        
        # Check the response
        assert response.status_code == 200
        assert response.json() == {"status": "success", "message": "Training completed"}
        mock_q_learning_agent.train.assert_called_once()
    
    def test_get_convergence_metrics_endpoint(self, client, mock_q_learning_agent):
        """Test the get_convergence_metrics endpoint"""
        # Mock the agent response
        mock_metrics = {
            "converged": False,
            "episodes": 100,
            "average_reward": 0.75
        }
        mock_q_learning_agent.get_convergence_metrics.return_value = mock_metrics
        
        # Make the request
        response = client.get("/q_learning/convergence_metrics")
        
        # Check the response
        assert response.status_code == 200
        assert response.json() == mock_metrics
        mock_q_learning_agent.get_convergence_metrics.assert_called_once()


# Helper class for async mocking
class AsyncMock(Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


if __name__ == "__main__":
    pytest.main([__file__])