"""
Unit tests for the Orchestrator agent's call_thinker method.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import requests
import json

# Add the orchestrator directory to the path so we can import the orchestrator agent
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "../../../../ece/agents/tier1/orchestrator"
        )
    ),
)

from orchestrator_agent import OrchestratorAgent


class TestOrchestratorCallThinker(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an instance of OrchestratorAgent with mock Redis settings
        self.orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

    def test_call_thinker_unregistered(self):
        """Test calling a Thinker that is not registered."""
        # Don't register any thinkers

        # Try to call an unregistered thinker
        result = self.orchestrator.call_thinker("math", "Calculate 2 + 2")

        # Verify the result
        self.assertIsNone(result)

    @patch("orchestrator_agent.requests.post")
    def test_call_thinker_success(self, mock_post):
        """Test successfully calling a Thinker agent."""
        # Mock the response from the Thinker agent
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "The sum of 2 and 2 is 4.",
            "reasoning": "Simple addition.",
        }
        mock_post.return_value = mock_response

        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Call the thinker
        result = self.orchestrator.call_thinker("math", "Calculate 2 + 2")

        # Verify the result
        expected = {
            "result": "The sum of 2 and 2 is 4.",
            "reasoning": "Simple addition.",
        }
        self.assertEqual(result, expected)

        # Verify the request was made correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://math-thinker:8000/process")
        self.assertIn("json", kwargs)
        self.assertEqual(kwargs["json"]["prompt"], "Calculate 2 + 2")
        self.assertEqual(kwargs["json"]["context"], {})
        self.assertEqual(kwargs["timeout"], 30)

    @patch("orchestrator_agent.requests.post")
    def test_call_thinker_with_context(self, mock_post):
        """Test calling a Thinker agent with context."""
        # Mock the response from the Thinker agent
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "The sum of 2 and 2 is 4.",
            "reasoning": "Simple addition.",
        }
        mock_post.return_value = mock_response

        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Call the thinker with context
        context = {"previous_calculation": "1 + 1 = 2"}
        result = self.orchestrator.call_thinker("math", "Calculate 2 + 2", context)

        # Verify the result
        expected = {
            "result": "The sum of 2 and 2 is 4.",
            "reasoning": "Simple addition.",
        }
        self.assertEqual(result, expected)

        # Verify the request was made correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://math-thinker:8000/process")
        self.assertIn("json", kwargs)
        self.assertEqual(kwargs["json"]["prompt"], "Calculate 2 + 2")
        self.assertEqual(kwargs["json"]["context"], context)
        self.assertEqual(kwargs["timeout"], 30)

    @patch("orchestrator_agent.requests.post")
    def test_call_thinker_http_error(self, mock_post):
        """Test handling of HTTP errors when calling a Thinker agent."""
        # Mock an HTTP error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Call the thinker
        result = self.orchestrator.call_thinker("math", "Calculate 2 + 2")

        # Verify the result
        self.assertIsNone(result)

    @patch("orchestrator_agent.requests.post")
    def test_call_thinker_request_exception(self, mock_post):
        """Test handling of request exceptions when calling a Thinker agent."""
        # Mock a request exception
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Call the thinker
        result = self.orchestrator.call_thinker("math", "Calculate 2 + 2")

        # Verify the result
        self.assertIsNone(result)

    @patch("orchestrator_agent.requests.post")
    def test_call_thinker_json_decode_error(self, mock_post):
        """Test handling of JSON decode errors when calling a Thinker agent."""
        # Mock a response with invalid JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("JSON decode error")
        mock_post.return_value = mock_response

        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Call the thinker
        result = self.orchestrator.call_thinker("math", "Calculate 2 + 2")

        # Verify the result
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
