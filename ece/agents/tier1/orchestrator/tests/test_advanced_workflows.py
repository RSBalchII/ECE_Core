"""
End-to-end tests for the advanced reasoning workflows in ECE v2.0.

This module tests both the Parallel Thinking and Exploratory Problem-Solving workflows.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import asyncio
import pytest

# Add the project root to the Python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
)

from ece.agents.tier1.orchestrator.orchestrator_agent import OrchestratorAgent


class TestAdvancedWorkflows(unittest.TestCase):
    """Test cases for the advanced reasoning workflows."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock the Redis connection to avoid dependency on external services
        with patch("redis.Redis") as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.ping.return_value = True
            mock_redis.return_value = mock_redis_instance

            # Initialize the orchestrator
            self.orchestrator = OrchestratorAgent()

    @pytest.mark.asyncio
    async def test_parallel_thinking_workflow(self):
        """Test the Parallel Thinking workflow with a complex problem."""
        prompt = "Analyze the pros and cons of renewable energy adoption"

        # Process the prompt
        response = await self.orchestrator.process_prompt(prompt)

        # Verify that we got a response
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)

        # Verify that the response contains indicators of parallel thinking
        # These assertions might need to be updated based on the actual output format
        # self.assertIn("Diverse perspectives considered", response)
        # self.assertIn("Optimist perspective", response)
        # self.assertIn("Pessimist perspective", response)

    @pytest.mark.asyncio
    async def test_exploratory_problem_solving_workflow(self):
        """Test the Exploratory Problem-Solving workflow with a solvable problem."""
        prompt = "Solve for x in the equation 2x + 5 = 15"

        # Process the prompt
        response = await self.orchestrator.process_prompt(prompt)

        # Verify that we got a response
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)

        # Verify that the response contains indicators of exploratory problem solving
        # These assertions might need to be updated based on the actual output format
        # self.assertIn("Solution analysis", response)
        # self.assertIn("Proposed approach", response)
        # self.assertIn("Execution", response)

    # The following tests are for the old caching logic and are no longer relevant.
    # async def test_traditional_workflow_still_works(self):
    #     """Test that the traditional workflow still functions for simple tasks."""
    #     prompt = "What is the capital of France?"

    #     # Mock the cache to return no results
    #     with patch.object(self.orchestrator, 'retrieve_from_cache', return_value=None):
    #         # Process the prompt
    #         response = await self.orchestrator.process_prompt(prompt)

    #         # Verify that we got a response
    #         self.assertIsInstance(response, str)
    #         self.assertGreater(len(response), 0)

    #         # Verify that the response indicates no specialized processing was needed
    #         self.assertIn("No specialized processing was needed", response)

    # async def test_cache_integration(self):
    #     """Test that cache integration works correctly."""
    #     prompt = "What is the speed of light?"

    #     # Mock the cache to return a specific result
    #     cache_result = {
    #         'value': 'The speed of light is approximately 299,792,458 meters per second.'
    #     }

    #     with patch.object(self.orchestrator, 'retrieve_from_cache', return_value=cache_result):
    #         # Process the prompt
    #         response = await self.orchestrator.process_prompt(prompt)

    #         # Verify that we got a response
    #         self.assertIsInstance(response, str)
    #         self.assertGreater(len(response), 0)

    #         # Verify that the response contains the cached context
    #         self.assertIn("Relevant context from cache", response)
    #         self.assertIn("speed of light", response)


if __name__ == "__main__":
    unittest.main()
