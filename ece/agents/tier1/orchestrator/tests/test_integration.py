"""
Integration tests for the Orchestrator agent with a mock Thinker.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import the orchestrator module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator_agent import OrchestratorAgent


class TestOrchestratorIntegration(unittest.TestCase):
    """Integration tests for the Orchestrator agent."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.orchestrator = OrchestratorAgent()

    # The following tests are for the old integration logic and are no longer relevant.
    # @patch('orchestrator_agent.requests.post')
    # def test_process_prompt_with_thinker(self, mock_post):
    #     """Test processing a prompt that requires a Thinker agent."""
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

    #     # Process a prompt that requires the math Thinker
    #     prompt = "What is the square root of 144?"
    #     response = self.orchestrator.process_prompt(prompt)

    #     # Verify that the Thinker was called
    #     mock_post.assert_called_once()

    #     # Verify the response contains the expected content
    #     self.assertIn("Based on your query", response)
    #     self.assertIn("Answer from specialized agent", response)
    #     self.assertIn("The square root of 144 is 12.", response)

    # @patch('orchestrator_agent.OrchestratorAgent.retrieve_from_cache')
    # def test_process_prompt_with_cache(self, mock_retrieve):
    #     """Test processing a prompt with relevant cache context."""
    #     # Mock the cache response
    #     mock_retrieve.return_value = {
    #         'value': 'Previous conversation context about mathematics.'
    #     }

    #     # Process a prompt that doesn't require a Thinker
    #     prompt = "What is the weather like today?"
    #     response = self.orchestrator.process_prompt(prompt)

    #     # Verify that the cache was checked
    #     mock_retrieve.assert_called_once()

    #     # Verify the response contains the cached context
    #     self.assertIn("Based on your query", response)
    #     self.assertIn("Relevant context from cache", response)
    #     self.assertIn("Previous conversation context about mathematics", response)

    # @patch('orchestrator_agent.requests.post')
    # def test_process_prompt_no_thinker_no_cache(self, mock_post):
    #     """Test processing a prompt that doesn't require a Thinker and has no cache context."""
    #     # Mock no cache context
    #     with patch('orchestrator_agent.OrchestratorAgent.retrieve_from_cache') as mock_retrieve:
    #         mock_retrieve.return_value = None

    #         # Process a prompt that doesn't require a Thinker
    #         prompt = "What is the weather like today?"
    #         response = self.orchestrator.process_prompt(prompt)

    #         # Verify that no Thinker was called
    #         mock_post.assert_not_called()

    #         # Verify the response indicates no additional processing was needed
    #         self.assertIn("Based on your query", response)
    #         self.assertIn("No additional context or specialized processing was needed", response)


if __name__ == "__main__":
    unittest.main()
