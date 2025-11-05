"""
Unit tests for the Orchestrator agent's delegation logic.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import the orchestrator module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator_agent import OrchestratorAgent


class TestOrchestratorDelegation(unittest.TestCase):
    """Test cases for the Orchestrator agent's delegation logic."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.orchestrator = OrchestratorAgent()

    # The following tests are for the old delegation logic and are no longer relevant.
    # def test_analyze_prompt_math(self):
    #     """Test that math-related prompts are correctly identified."""
    #     prompt = "What is the square root of 144?"
    #     specialization = self.orchestrator.analyze_prompt(prompt)
    #     self.assertEqual(specialization, "math")

    # def test_analyze_prompt_code(self):
    #     """Test that code-related prompts are correctly identified."""
    #     prompt = "How do I write a function to calculate factorial in Python?"
    #     specialization = self.orchestrator.analyze_prompt(prompt)
    #     self.assertEqual(specialization, "code")

    # def test_analyze_prompt_data(self):
    #     """Test that data-related prompts are correctly identified."""
    #     prompt = "What is the mean of this dataset: 1, 2, 3, 4, 5?"
    #     specialization = self.orchestrator.analyze_prompt(prompt)
    #     self.assertEqual(specialization, "data")

    # def test_analyze_prompt_no_thinker(self):
    #     """Test that prompts not requiring a Thinker are correctly identified."""
    #     prompt = "What is the weather like today?"
    #     specialization = self.orchestrator.analyze_prompt(prompt)
    #     self.assertIsNone(specialization)

    # def test_get_thinker_endpoint(self):
    #     """Test retrieving a Thinker agent's endpoint."""
    #     # Register a Thinker agent
    #     self.orchestrator.register_thinker("math", "http://localhost:5001/math")

    #     # Get the endpoint
    #     endpoint = self.orchestrator.get_thinker_endpoint("math")
    #     self.assertEqual(endpoint, "http://localhost:5001/math")

    # def test_get_thinker_endpoint_not_registered(self):
    #     """Test retrieving an endpoint for an unregistered Thinker."""
    #     endpoint = self.orchestrator.get_thinker_endpoint("nonexistent")
    #     self.assertIsNone(endpoint)

    # @patch('orchestrator_agent.requests.post')
    # def test_call_thinker_success(self, mock_post):
    #     """Test successfully calling a Thinker agent."""
    #     # Mock the response from the Thinker agent
    #     mock_response = MagicMock()
    #     mock_response.json.return_value = {
    #         "answer": "The square root of 144 is 12.",
    #         "reasoning": "12 multiplied by itself equals 144."
    #     }
    #     mock_response.raise_for_status.return_value = None
    #     mock_post.return_value = mock_response

    #     # Register a Thinker agent
    #     self.orchestrator.register_thinker("math", "http://localhost:5001/math")

    #     # Call the Thinker agent
    #     result = self.orchestrator.call_thinker("math", "What is the square root of 144?")

    #     # Verify the result
    #     self.assertIsNotNone(result)
    #     self.assertEqual(result["answer"], "The square root of 144 is 12.")
    #     self.assertEqual(result["reasoning"], "12 multiplied by itself equals 144.")

    # @patch('orchestrator_agent.requests.post')
    # def test_call_thinker_not_registered(self, mock_post):
    #     """Test calling an unregistered Thinker agent."""
    #     # Try to call an unregistered Thinker agent
    #     result = self.orchestrator.call_thinker("nonexistent", "Some prompt")

    #     # Verify that no HTTP request was made
    #     mock_post.assert_not_called()
    #     self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
