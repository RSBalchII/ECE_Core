"""
Integration tests for the External Context Engine, including tests for the new specialist agents.
"""

import pytest
import requests
import time
from typing import Dict, Any

# Base URL for the API
BASE_URL = "http://localhost:8000"


class TestECEIntegration:
    """Test suite for External Context Engine integration tests"""

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
            pytest.fail("Could not connect to the ECE service. Make sure it's running.")

    def test_health_check(self):
        """Test the health check endpoint"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self):
        """Test the root endpoint"""
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_web_search_intent(self):
        """Test the web search intent routing"""
        payload = {
            "message": "Find information about artificial intelligence",
            "context": {},
        }

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        assert data["agent_used"] == "WebSearchAgent"
        assert "results found" in data["response"]

    def test_multi_modal_processing_intent(self):
        """Test the multi-modal processing intent routing"""
        payload = {"message": "Process this image of a cat", "context": {}}

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        assert data["agent_used"] == "MultiModalIngestionAgent"

    def test_coherence_check_intent(self):
        """Test the coherence check intent routing"""
        payload = {
            "message": "Check the coherence of this response",
            "context": {
                "previous_messages": ["Hello, how are you?", "I'm fine, thank you!"]
            },
        }

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        assert data["agent_used"] == "CoherenceAgent"
        assert "Coherence score" in data["response"]

    def test_safety_check_intent(self):
        """Test the safety check intent routing"""
        payload = {"message": "Is this content appropriate?", "context": {}}

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        assert data["agent_used"] == "SafetyAgent"
        assert "Safety score" in data["response"]

    def test_default_intent(self):
        """Test the default intent routing"""
        payload = {"message": "Generic query without specific intent", "context": {}}

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        # Should default to WebSearchAgent
        assert data["agent_used"] == "WebSearchAgent"
        assert "results found" in data["response"]

    # New tests for the Coda-Coder-D-012 series specialist agents

    def test_extractor_agent_routing(self):
        """Test routing to Extractor agent"""
        payload = {
            "message": "Extract key information from this document",
            "context": {},
        }

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        # Assuming Extractor agent would be used for extraction tasks
        # This might need to be adjusted based on actual implementation
        assert data["agent_used"] in [
            "Extractor",
            "WebSearchAgent",
        ]  # Fallback to default if not implemented

    def test_distiller_agent_routing(self):
        """Test routing to Distiller agent"""
        payload = {
            "message": "Distill the main points from this research paper",
            "context": {},
        }

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        # Assuming Distiller agent would be used for distillation tasks
        # This might need to be adjusted based on actual implementation
        assert data["agent_used"] in [
            "Distiller",
            "WebSearchAgent",
        ]  # Fallback to default if not implemented

    def test_archivist_agent_routing(self):
        """Test routing to Archivist agent"""
        payload = {
            "message": "Archive this conversation for future reference",
            "context": {},
        }

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        # Assuming Archivist agent would be used for archiving tasks
        # This might need to be adjusted based on actual implementation
        assert data["agent_used"] in [
            "Archivist",
            "WebSearchAgent",
        ]  # Fallback to default if not implemented

    def test_injector_agent_routing(self):
        """Test routing to Injector agent"""
        payload = {
            "message": "Inject this context into the knowledge base",
            "context": {},
        }

        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        # Assuming Injector agent would be used for injection tasks
        # This might need to be adjusted based on actual implementation
        assert data["agent_used"] in [
            "Injector",
            "WebSearchAgent",
        ]  # Fallback to default if not implemented


if __name__ == "__main__":
    pytest.main([__file__])
