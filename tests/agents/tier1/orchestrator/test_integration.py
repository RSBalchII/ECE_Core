"""
Integration tests for the Orchestrator agent with a mock Thinker.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Import the orchestrator agent directly
from orchestrator_agent import OrchestratorAgent


class TestOrchestratorIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an instance of OrchestratorAgent with mock Redis settings
        self.orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

    @patch("orchestrator_agent.requests.post")
    def test_process_prompt_with_math_thinker(self, mock_post):
        """Test processing a prompt that requires a math thinker."""
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

        # Process a prompt that should trigger the math thinker
        prompt = "Calculate 2 + 2"
        result = self.orchestrator.process_prompt(prompt)

        # Verify the result
        self.assertEqual(result, "The sum of 2 and 2 is 4.")

        # Verify the request was made correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://math-thinker:8000/process")
        self.assertIn("json", kwargs)
        self.assertEqual(kwargs["json"]["prompt"], prompt)

    @patch("orchestrator_agent.requests.post")
    def test_process_prompt_with_code_thinker(self, mock_post):
        """Test processing a prompt that requires a code thinker."""
        # Mock the response from the Thinker agent
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "Here is a simple Python function:\n\ndef add(a, b):\n    return a + b",
            "reasoning": "Creating a basic addition function.",
        }
        mock_post.return_value = mock_response

        # Register a code thinker
        self.orchestrator.register_thinker("code", "http://code-thinker:8000")

        # Process a prompt that should trigger the code thinker
        prompt = "How do I write a function to add two numbers in Python?"
        result = self.orchestrator.process_prompt(prompt)

        # Verify the result
        self.assertEqual(
            result,
            "Here is a simple Python function:\n\ndef add(a, b):\n    return a + b",
        )

        # Verify the request was made correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://code-thinker:8000/process")
        self.assertIn("json", kwargs)
        self.assertEqual(kwargs["json"]["prompt"], prompt)

    @patch("orchestrator_agent.requests.post")
    def test_process_prompt_with_unavailable_thinker(self, mock_post):
        """Test processing a prompt when the required thinker is unavailable."""
        # Mock a failed response from the Thinker agent
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Process a prompt that should trigger the math thinker
        prompt = "Calculate 2 + 2"
        result = self.orchestrator.process_prompt(prompt)

        # Verify we get a default response since the thinker failed
        self.assertIn("I've processed your prompt", result)

        # Verify the request was made
        mock_post.assert_called_once()

    @patch("orchestrator_agent.requests.post")
    def test_process_prompt_without_specialized_reasoning(self, mock_post):
        """Test processing a prompt that doesn't require specialized reasoning."""
        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Process a prompt that shouldn't trigger any specialized reasoning
        prompt = "What is the weather like today?"
        result = self.orchestrator.process_prompt(prompt)

        # Verify the result
        self.assertIn("I've processed your prompt", result)

        # Verify no request was made to a thinker
        mock_post.assert_not_called()

    @patch("orchestrator_agent.redis.Redis")
    def test_process_prompt_with_context(self, mock_redis):
        """Test processing a prompt with context from the cache."""
        # Mock the Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = (
            '{"previous_query": "What is the capital of France?"}'
        )
        mock_redis.return_value = mock_redis_client

        # Reinitialize the orchestrator with the mocked Redis
        orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

        # Register a thinker
        orchestrator.register_thinker("research", "http://research-thinker:8000")

        # Process a prompt with a context key
        prompt = "What is the population of that city?"
        result = orchestrator.process_prompt(prompt, context_key="session_123")

        # Verify the Redis client was called correctly
        mock_redis_client.get.assert_called_once_with("session_123")


if __name__ == "__main__":
    unittest.main()
