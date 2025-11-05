"""
Unit tests for the Orchestrator agent's delegation logic.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Import the orchestrator agent directly
from orchestrator_agent import OrchestratorAgent


class TestOrchestratorDelegation(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an instance of OrchestratorAgent with mock Redis settings
        self.orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

    def test_register_thinker(self):
        """Test registering a thinker agent."""
        # Register a thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Verify it's in the registry
        self.assertIn("math", self.orchestrator.thinker_registry)
        self.assertEqual(
            self.orchestrator.thinker_registry["math"], "http://math-thinker:8000"
        )

    def test_unregister_thinker(self):
        """Test unregistering a thinker agent."""
        # Register a thinker first
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Unregister it
        result = self.orchestrator.unregister_thinker("math")

        # Verify it was unregistered
        self.assertTrue(result)
        self.assertNotIn("math", self.orchestrator.thinker_registry)

        # Try to unregister a non-existent thinker
        result = self.orchestrator.unregister_thinker("nonexistent")
        self.assertFalse(result)

    def test_get_thinker_endpoint(self):
        """Test getting a thinker endpoint."""
        # Register a thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Get the endpoint
        endpoint = self.orchestrator.get_thinker_endpoint("math")

        # Verify it's correct
        self.assertEqual(endpoint, "http://math-thinker:8000")

        # Try to get a non-existent thinker
        endpoint = self.orchestrator.get_thinker_endpoint("nonexistent")
        self.assertIsNone(endpoint)

    def test_list_available_thinkers(self):
        """Test listing available thinkers."""
        # Register some thinkers
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")
        self.orchestrator.register_thinker("code", "http://code-thinker:8000")

        # Get the list
        thinkers = self.orchestrator.list_available_thinkers()

        # Verify it contains the registered thinkers
        self.assertIn("math", thinkers)
        self.assertIn("code", thinkers)
        self.assertEqual(len(thinkers), 2)

    def test_analyze_prompt_math(self):
        """Test analyzing a prompt that requires math reasoning."""
        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Test a prompt that should trigger math reasoning
        prompt = "Calculate 2 + 2"
        result = self.orchestrator.analyze_prompt(prompt)

        # Verify it correctly identifies the need for math reasoning
        self.assertEqual(result, "math")

        # Test another prompt that should trigger math reasoning
        prompt = "What is 2 plus 2?"
        result = self.orchestrator.analyze_prompt(prompt)

        # Verify it correctly identifies the need for math reasoning
        self.assertEqual(result, "math")

    def test_analyze_prompt_code(self):
        """Test analyzing a prompt that requires code reasoning."""
        # Register a code thinker
        self.orchestrator.register_thinker("code", "http://code-thinker:8000")

        # Test a prompt that should trigger code reasoning
        prompt = "How do I write a function in Python?"
        result = self.orchestrator.analyze_prompt(prompt)

        # Verify it correctly identifies the need for code reasoning
        self.assertEqual(result, "code")

    def test_analyze_prompt_no_specialization(self):
        """Test analyzing a prompt that doesn't require specialized reasoning."""
        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Test a prompt that shouldn't trigger any specialized reasoning
        prompt = "What is the weather like today?"
        result = self.orchestrator.analyze_prompt(prompt)

        # Verify it correctly identifies that no specialized reasoning is needed
        self.assertIsNone(result)

    def test_analyze_prompt_unavailable_thinker(self):
        """Test analyzing a prompt for an unavailable thinker."""
        # Don't register any thinkers

        # Test a prompt that would normally trigger math reasoning
        prompt = "What is 2 + 2?"
        result = self.orchestrator.analyze_prompt(prompt)

        # Verify it returns None because the math thinker isn't registered
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
