"""
Unit tests for the Orchestrator agent's context management functionality.
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


class TestOrchestratorContextManagement(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an instance of OrchestratorAgent with mock Redis settings
        self.orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

    @patch("orchestrator_agent.redis.Redis")
    def test_store_context_success(self, mock_redis):
        """Test successfully storing context in Redis."""
        # Mock the Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.setex.return_value = True
        mock_redis.return_value = mock_redis_client

        # Reinitialize the orchestrator with the mocked Redis
        orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

        # Test data
        key = "test_key"
        context = {"user_id": 123, "session_data": "test_data"}

        # Store context
        result = orchestrator.store_context(key, context)

        # Verify the result
        self.assertTrue(result)

        # Verify the Redis client was called correctly
        mock_redis_client.setex.assert_called_once()
        args, kwargs = mock_redis_client.setex.call_args
        self.assertEqual(args[0], key)
        self.assertEqual(args[2], json.dumps(context))

    @patch("orchestrator_agent.redis.Redis")
    def test_store_context_failure(self, mock_redis):
        """Test handling of failure when storing context in Redis."""
        # Mock the Redis client to raise an exception
        mock_redis_client = MagicMock()
        mock_redis_client.setex.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_redis_client

        # Reinitialize the orchestrator with the mocked Redis
        orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

        # Test data
        key = "test_key"
        context = {"user_id": 123, "session_data": "test_data"}

        # Store context
        result = orchestrator.store_context(key, context)

        # Verify the result
        self.assertFalse(result)

    @patch("orchestrator_agent.redis.Redis")
    def test_retrieve_context_success(self, mock_redis):
        """Test successfully retrieving context from Redis."""
        # Mock the Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = (
            '{"user_id": 123, "session_data": "test_data"}'
        )
        mock_redis.return_value = mock_redis_client

        # Reinitialize the orchestrator with the mocked Redis
        orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

        # Test data
        key = "test_key"

        # Retrieve context
        result = orchestrator.retrieve_context(key)

        # Verify the result
        expected = {"user_id": 123, "session_data": "test_data"}
        self.assertEqual(result, expected)

        # Verify the Redis client was called correctly
        mock_redis_client.get.assert_called_once_with(key)

    @patch("orchestrator_agent.redis.Redis")
    def test_retrieve_context_not_found(self, mock_redis):
        """Test retrieving context when key doesn't exist in Redis."""
        # Mock the Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        # Reinitialize the orchestrator with the mocked Redis
        orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

        # Test data
        key = "nonexistent_key"

        # Retrieve context
        result = orchestrator.retrieve_context(key)

        # Verify the result
        self.assertIsNone(result)

    @patch("orchestrator_agent.redis.Redis")
    def test_retrieve_context_json_error(self, mock_redis):
        """Test handling of JSON decode error when retrieving context."""
        # Mock the Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = '{"invalid_json": }'  # Invalid JSON
        mock_redis.return_value = mock_redis_client

        # Reinitialize the orchestrator with the mocked Redis
        orchestrator = OrchestratorAgent(
            redis_host="localhost", redis_port=6379, redis_db=0
        )

        # Test data
        key = "test_key"

        # Retrieve context
        result = orchestrator.retrieve_context(key)

        # Verify the result
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
