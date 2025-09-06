"""
Integration tests for the ExtractorAgent.
"""
import pytest
import requests
import time
import os
import tempfile
from typing import Dict, Any

# Base URL for the API
BASE_URL = "http://localhost:8000"


class TestExtractorAgentIntegration:
    """Test suite for ExtractorAgent integration tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup method to ensure the service is running before tests"""
        # Wait a bit for the service to start
        time.sleep(2)
        
        # Check if service is running
        try:
            response = requests.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip("Could not connect to the ECE service. Make sure it's running.")
    
    def test_create_temp_text_file(self):
        """Helper method to create a temporary text file for testing"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as temp_file:
            temp_file.write("John Doe can be reached at john.doe@example.com. The meeting is on 12/25/2023.")
            return temp_file.name
    
    def test_successful_extraction_from_text_file(self):
        """Test successful extraction from a text file"""
        # Create a temporary text file
        temp_file_path = self.test_create_temp_text_file()
        
        try:
            # Prepare the payload for extraction
            payload = {
                "message": f"Extract information from this file: {temp_file_path}",
                "context": {
                    "data_source": temp_file_path,
                    "data_type": "text",
                    "criteria": {}
                }
            }
            
            # Since we haven't integrated the agent yet, we'll test the chat endpoint
            # and check if it properly routes to our agent once integrated
            response = requests.post(f"{BASE_URL}/chat", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            assert "response" in data
            # For now, it will likely use the default agent until we integrate the ExtractorAgent
            # We'll update this test after integration
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_extraction_with_keywords_criteria(self):
        """Test extraction with keywords criteria"""
        # Create a temporary text file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as temp_file:
            temp_file.write("The project deadline is approaching. We need to complete the project by Friday. The budget is $50,000.")
            temp_file_path = temp_file.name
        
        try:
            payload = {
                "message": f"Extract information about project deadlines and budget from: {temp_file_path}",
                "context": {
                    "data_source": temp_file_path,
                    "data_type": "text",
                    "criteria": {
                        "keywords": ["project", "deadline", "budget"]
                    }
                }
            }
            
            response = requests.post(f"{BASE_URL}/chat", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            assert "response" in data
            # For now, it will likely use the default agent until we integrate the ExtractorAgent
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_extraction_error_handling(self):
        """Test error handling for non-existent file"""
        payload = {
            "message": "Extract information from this file: /non/existent/file.txt",
            "context": {
                "data_source": "/non/existent/file.txt",
                "data_type": "text",
                "criteria": {}
            }
        }
        
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        # The service should handle errors gracefully
        assert response.status_code == 200  # Service should not crash
        
        data = response.json()
        assert "response" in data
        # Response will depend on which agent handles it


if __name__ == "__main__":
    pytest.main([__file__])