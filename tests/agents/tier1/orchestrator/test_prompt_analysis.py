"""
Unit tests for the Orchestrator agent's prompt analysis functionality.
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


class TestOrchestratorPromptAnalysis(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an instance of OrchestratorAgent with mock Redis settings
        self.orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

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

    def test_analyze_prompt_research(self):
        """Test analyzing a prompt that requires research reasoning."""
        # Register a research thinker
        self.orchestrator.register_thinker("research", "http://research-thinker:8000")

        # Test a prompt that should trigger research reasoning
        prompt = "Find information about climate change"
        result = self.orchestrator.analyze_prompt(prompt)

        # Verify it correctly identifies the need for research reasoning
        self.assertEqual(result, "research")

    def test_analyze_prompt_writing(self):
        """Test analyzing a prompt that requires writing reasoning."""
        # Register a writing thinker
        self.orchestrator.register_thinker("writing", "http://writing-thinker:8000")

        # Test a prompt that should trigger writing reasoning
        prompt = "Write a story about a robot"
        result = self.orchestrator.analyze_prompt(prompt)

        # Verify it correctly identifies the need for writing reasoning
        self.assertEqual(result, "writing")

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

    def test_analyze_prompt_case_insensitive(self):
        """Test that prompt analysis is case insensitive."""
        # Register a math thinker
        self.orchestrator.register_thinker("math", "http://math-thinker:8000")

        # Test prompts with different cases
        prompts = [
            "CALCULATE 2 + 2",
            "Calculate 2 + 2",
            "calculate 2 + 2",
            "CaLcUlAtE 2 + 2",
        ]

        for prompt in prompts:
            result = self.orchestrator.analyze_prompt(prompt)
            self.assertEqual(result, "math", f"Failed for prompt: {prompt}")


if __name__ == "__main__":
    unittest.main()
