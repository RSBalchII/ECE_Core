"""
Unit tests for the Orchestrator agent's thought loop processing functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

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


class TestOrchestratorThoughtLoopProcessing(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an instance of OrchestratorAgent with mock Redis settings
        self.orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

    @patch("orchestrator_agent.OrchestratorAgent.process_prompt")
    @patch("orchestrator_agent.OrchestratorAgent.store_context")
    @patch("orchestrator_agent.OrchestratorAgent.retrieve_context")
    def test_process_thought_loop(
        self, mock_retrieve_context, mock_store_context, mock_process_prompt
    ):
        """Test processing a prompt through a thought loop."""
        # Mock the process_prompt method to return a specific response
        mock_process_prompt.return_value = "The sum of 2 and 2 is 4."

        # Mock the retrieve_context method to return a specific context
        mock_retrieve_context.return_value = {
            "previous_response": "The sum of 2 and 2 is 4.",
            "iteration": 0,
        }

        # Test data
        initial_prompt = "Calculate 2 + 2"

        # Process the thought loop
        result = self.orchestrator.process_thought_loop(
            initial_prompt, max_iterations=3
        )

        # Verify the result
        # In the current implementation, it should return the synthesized response based on the final context
        expected = 'Based on the context I found: {"previous_response": "The sum of 2 and 2 is 4.", "iteration": 0}'
        self.assertEqual(result, expected)

        # Verify that process_prompt was called
        mock_process_prompt.assert_called_once_with(
            initial_prompt, f"thought_loop_{hash(initial_prompt)}"
        )

        # Verify that store_context was called
        mock_store_context.assert_called_once()

        # Verify that retrieve_context was called
        mock_retrieve_context.assert_called_once_with(
            f"thought_loop_{hash(initial_prompt)}"
        )


if __name__ == "__main__":
    unittest.main()
