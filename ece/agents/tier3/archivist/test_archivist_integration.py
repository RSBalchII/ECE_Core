"""
Integration tests for the Archivist agent
"""
import unittest
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Add the project root directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from ece.agents.tier3.archivist.archivist_agent import app, ContextRequest

class TestArchivistIntegration(unittest.TestCase):
    """Integration tests for the Archivist agent."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = app
        # Create a test client using the FastAPI app
        from fastapi.testclient import TestClient
        self.client = TestClient(self.app)
    
    def test_health_check(self):
        """Test the health check endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})
    
    def test_root_endpoint(self):
        """Test the root endpoint."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())
    
    def test_context_request(self):
        """Test the context request endpoint."""
        # Create a context request
        context_request = ContextRequest(
            query="Test query for context",
            user_id="test_user"
        )
        
        # Send the request to the context endpoint
        response = self.client.post("/context", json=context_request.dict())
        
        # Check that we get a response
        self.assertEqual(response.status_code, 200)
        
        # Check that the response has the expected structure
        response_data = response.json()
        self.assertIn("context", response_data)
        self.assertIn("metadata", response_data)
        
        # Check metadata
        metadata = response_data["metadata"]
        self.assertIn("query", metadata)
        self.assertIn("timestamp", metadata)
        self.assertIn("source", metadata)
        self.assertIn("paths_found", metadata)
        self.assertIn("paths_returned", metadata)
        
        # Check that context is a list
        context = response_data["context"]
        self.assertIsInstance(context, list)
    
    def test_distiller_data_endpoint(self):
        """Test the distiller data endpoint."""
        # Create test distiller data
        test_data = {
            "entities": [
                {
                    "id": "test_entity_1",
                    "type": "Concept",
                    "properties": {
                        "name": "Test Concept",
                        "description": "A test concept for integration testing"
                    }
                }
            ],
            "relationships": [
                {
                    "start_id": "test_entity_1",
                    "start_type": "Concept",
                    "end_id": "test_entity_2",
                    "end_type": "Concept",
                    "type": "RELATED_TO",
                    "properties": {
                        "strength": 0.8
                    }
                }
            ],
            "summary": "Test data for integration testing"
        }
        
        with patch('ece.agents.tier3.archivist.archivist_agent.injector_client') as mock_injector_client, \
             patch('ece.agents.tier3.archivist.archivist_agent.qlearning_client') as mock_qlearning_client, \
             patch('ece.agents.tier3.archivist.archivist_agent.distiller_client') as mock_distiller_client:
            
            # Mock the send_data_for_injection method to return a success response
            mock_injector_client.send_data_for_injection = AsyncMock(return_value={"success": True, "status": "processed", "memory_node_id": 123})
            # Mock the refine_relationships method
            mock_qlearning_client.refine_relationships = AsyncMock(return_value={"status": "success"})
            # Mock the process_text method
            mock_distiller_client.process_text = AsyncMock(return_value={
                "entities": [{"id": "test_entity_1", "type": "Concept", "properties": {"name": "Test Concept"}}],
                "relationships": [],
                "summary": "test summary",
                "timestamp": "2023-01-01T00:00:00"
            })
            
            # Mock get_or_create_timenode and link_memory_to_timenode
            mock_injector_client.get_or_create_timenode = AsyncMock(return_value={"success": True})
            mock_injector_client.link_memory_to_timenode = AsyncMock(return_value=True)

            # Send the request to the distiller data endpoint
            response = self.client.post("/internal/data_to_archive", json=test_data)
            
            # Check that we get a successful response
            self.assertEqual(response.status_code, 200)
            response_data = response.json()
            self.assertEqual(response_data["status"], "processed")

    def test_handle_truncated_entries(self):
        """Test the handle_truncated_entries endpoint."""
        # Create a list of truncated keys
        truncated_keys = ["context_cache:key1", "context_cache:key2"]
        
        with patch('ece.agents.tier3.archivist.archivist_agent.redis_client') as mock_redis_client, \
             patch('ece.agents.tier3.archivist.archivist_agent.distiller_client') as mock_distiller_client, \
             patch('ece.agents.tier3.archivist.archivist_agent.injector_client') as mock_injector_client, \
             patch('ece.agents.tier3.archivist.archivist_agent.qlearning_client') as mock_qlearning_client:
            
            # Mock the hgetall method to return a value
            mock_redis_client.hgetall.return_value = {"value": "test_value", "created_at": "2023-01-01T00:00:00"}
            
            # Mock distiller_client.process_text
            mock_distiller_client.process_text = AsyncMock(return_value={
                "entities": [{"id": "test_entity_1", "type": "Concept", "properties": {"name": "Test Concept"}}],
                "relationships": [],
                "summary": "test summary",
                "timestamp": "2023-01-01T00:00:00"
            })
            
            # Mock injector_client.send_data_for_injection
            mock_injector_client.send_data_for_injection = AsyncMock(return_value={"success": True, "status": "processed", "memory_node_id": 123})
            
            # Mock qlearning_client.refine_relationships
            mock_qlearning_client.refine_relationships = AsyncMock(return_value={"status": "success"})
            
            # Mock get_or_create_timenode and link_memory_to_timenode
            mock_injector_client.get_or_create_timenode = AsyncMock(return_value={"success": True})
            mock_injector_client.link_memory_to_timenode = AsyncMock(return_value=True)

            # Send the request to the endpoint
            response = self.client.post("/internal/handle_truncated_entries", json=truncated_keys)
            
            # Check that we get a successful response
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "processed"})
            
            # Verify that refine_relationships was called for each truncated key
            self.assertEqual(mock_qlearning_client.refine_relationships.call_count, len(truncated_keys))

if __name__ == "__main__":
    unittest.main()