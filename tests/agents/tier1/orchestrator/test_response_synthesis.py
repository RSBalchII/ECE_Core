"""
Unit tests for the Orchestrator agent's response synthesis functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
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


class TestOrchestratorResponseSynthesis(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an instance of OrchestratorAgent with mock Redis settings
        self.orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

    def test_synthesize_response_with_thinker_response(self):
        """Test synthesizing a response with a thinker response."""
        prompt = "Calculate 2 + 2"
        cache_context = None
        thinker_response = {
            "result": "The sum of 2 and 2 is 4.",
            "reasoning": "Simple addition.",
        }

        result = self.orchestrator.synthesize_response(
            prompt, cache_context, thinker_response
        )

        # Verify the result
        self.assertEqual(result, "The sum of 2 and 2 is 4.")

    def test_synthesize_response_with_cache_context(self):
        """Test synthesizing a response with cache context but no thinker response."""
        prompt = "What is the capital of France?"
        cache_context = {"previous_query": "What is the capital of France?"}
        thinker_response = None

        result = self.orchestrator.synthesize_response(
            prompt, cache_context, thinker_response
        )

        # Verify the result contains the cache context
        self.assertIn("Based on the context I found", result)
        self.assertIn(json.dumps(cache_context), result)

    def test_synthesize_response_fallback(self):
        """Test the fallback response when no thinker response or cache context is available."""
        prompt = "Hello, Orchestrator!"
        cache_context = None
        thinker_response = None

        result = self.orchestrator.synthesize_response(
            prompt, cache_context, thinker_response
        )

        # Verify the result is the fallback response
        self.assertIn("I've processed your prompt", result)
        self.assertIn(prompt, result)

    def test_synthesize_response_thinker_response_without_result(self):
        """Test synthesizing a response with a thinker response that doesn't have a 'result' key."""
        prompt = "Calculate 2 + 2"
        cache_context = None
        thinker_response = {"reasoning": "Simple addition."}

        result = self.orchestrator.synthesize_response(
            prompt, cache_context, thinker_response
        )

        # Should fall back to the default response since there's no 'result' key
        self.assertIn("I've processed your prompt", result)
        self.assertIn(prompt, result)


if __name__ == "__main__":
    unittest.main()
