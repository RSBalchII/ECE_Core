"""
Integration tests for the DistillerAgent with the main application
"""

import sys
import os
import pytest
import requests
import time
from typing import Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

class TestDistillerAgentIntegration:
    """Integration tests for the DistillerAgent with the main application"""
    
    BASE_URL = "http://localhost:8001"
    
    @classmethod
    def setup_class(cls):
        """Set up test class"""
        # Start the server in the background
        import subprocess
        import atexit
        
        # Start the server
        cls.server_process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "src.external_context_engine.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8001"
        ], cwd="/home/rsbiiw/projects/External-Context-Engine")
        
        # Give the server time to start
        time.sleep(5)
        
        # Register cleanup function
        atexit.register(cls.cleanup)
    
    @classmethod
    def cleanup(cls):
        """Clean up after tests"""
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            cls.server_process.wait()
    
    def test_health_check(self):
        """Test the health check endpoint"""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_distill_endpoint(self):
        """Test the distill endpoint"""
        text = "Google was founded by Larry Page and Sergey Brin while they were Ph.D. students at Stanford University."
        payload = {
            "text": text,
            "context": {}
        }
        
        response = requests.post(f"{self.BASE_URL}/distill", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "entities" in data
        assert "relationships" in data
        assert "key_points" in data
        assert "metadata" in data
        
        # Check that entities were extracted
        assert len(data["entities"]) > 0
        
        # Check metadata
        metadata = data["metadata"]
        assert metadata["agent"] == "DistillerAgent"
        assert metadata["text_length"] == len(text)
        # Note: processing_time_seconds might not always be present in cached results
        assert "entities_count" in metadata
        assert "relationships_count" in metadata
        assert "key_points_count" in metadata
    
    def test_chat_endpoint_with_distill_intent(self):
        """Test the chat endpoint with distill intent"""
        message = "Distill this text: Google was founded by Larry Page and Sergey Brin while they were Ph.D. students at Stanford University."
        payload = {
            "message": message,
            "context": {}
        }
        
        response = requests.post(f"{self.BASE_URL}/chat", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        assert data["agent_used"] == "DistillerAgent"
        
        # Check that the response mentions distillation results
        assert "entities" in data["response"].lower() or "distilled" in data["response"].lower()
    
    def test_distill_endpoint_with_empty_text(self):
        """Test the distill endpoint with empty text"""
        payload = {
            "text": "",
            "context": {}
        }
        
        response = requests.post(f"{self.BASE_URL}/distill", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "entities" in data
        assert "metadata" in data
    
    def test_distill_endpoint_with_large_text(self):
        """Test the distill endpoint with large text"""
        large_text = "This is a sample sentence. " * 1000
        payload = {
            "text": large_text,
            "context": {}
        }
        
        response = requests.post(f"{self.BASE_URL}/distill", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["metadata"]["text_length"] == len(large_text)

if __name__ == "__main__":
    pytest.main([__file__])