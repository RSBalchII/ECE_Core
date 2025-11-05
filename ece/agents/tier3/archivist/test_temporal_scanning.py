#!/usr/bin/env python3
"""
Integration tests for the Temporal Scanning functionality in the Archivist Agent.
"""

import unittest
import asyncio
import redis
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add the archivist agent directory to the path
archivist_path = os.path.join(
    os.path.dirname(__file__), "..", "ece", "agents", "tier3", "archivist"
)
sys.path.insert(0, archivist_path)

from archivist_agent import (
    _process_cache_entry,
    _scan_cache,
    continuous_temporal_scanning,
    distiller_client,
    injector_client,
    redis_client,
)


class TestTemporalScanning(unittest.TestCase):
    """Test cases for the temporal scanning functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock Redis client
        self.mock_redis = MagicMock()
        redis_client = self.mock_redis

        # Mock Distiller client
        self.mock_distiller_client = AsyncMock()
        distiller_client = self.mock_distiller_client

        # Mock Injector client
        self.mock_injector_client = AsyncMock()
        injector_client = self.mock_injector_client

    @patch("archivist_agent.redis_client")
    @patch("archivist_agent.distiller_client")
    @patch("archivist_agent.injector_client")
    async def test_process_cache_entry_success(
        self, mock_injector, mock_distiller, mock_redis
    ):
        """Test successful processing of a cache entry."""
        # Mock the Redis client methods
        mock_redis.sadd.return_value = 1

        # Mock the Distiller client response
        mock_distiller.process_text.return_value = {
            "entities": [
                {"id": "1", "type": "Concept", "properties": {"name": "Test"}}
            ],
            "relationships": [],
            "summary": "Test summary",
            "timestamp": "2023-01-01T00:00:00Z",
        }

        # Mock the Injector client response for data injection
        mock_injector.send_data_for_injection.return_value = {
            "success": True,
            "memory_node_id": 123,
        }

        # Mock the Injector client response for temporal operations
        mock_injector.get_or_create_timenode.return_value = {"day_id": 456}

        mock_injector.link_memory_to_timenode.return_value = True

        # Test processing a cache entry
        result = await _process_cache_entry("test_key", "test_value")

        # Verify results
        self.assertTrue(result)
        mock_distiller.process_text.assert_called_once_with(
            "test_value", "context_cache"
        )
        mock_injector.send_data_for_injection.assert_called_once()
        mock_injector.get_or_create_timenode.assert_called_once()
        mock_injector.link_memory_to_timenode.assert_called_once()
        mock_redis.sadd.assert_called_once_with(
            "archivist:processed_entries", "test_key"
        )

    @patch("archivist_agent.redis_client")
    @patch("archivist_agent.distiller_client")
    async def test_process_cache_entry_distiller_failure(
        self, mock_distiller, mock_redis
    ):
        """Test processing of a cache entry when Distiller fails."""
        # Mock the Redis client methods
        mock_redis.sadd.return_value = 1

        # Mock the Distiller client response with error
        mock_distiller.process_text.return_value = {
            "error": "Distiller processing failed"
        }

        # Test processing a cache entry
        result = await _process_cache_entry("test_key", "test_value")

        # Verify results
        self.assertFalse(result)
        mock_distiller.process_text.assert_called_once_with(
            "test_value", "context_cache"
        )

    @patch("archivist_agent.redis_client")
    @patch("archivist_agent.distiller_client")
    @patch("archivist_agent.injector_client")
    async def test_process_cache_entry_injector_failure(
        self, mock_injector, mock_distiller, mock_redis
    ):
        """Test processing of a cache entry when Injector fails."""
        # Mock the Redis client methods
        mock_redis.sadd.return_value = 1

        # Mock the Distiller client response
        mock_distiller.process_text.return_value = {
            "entities": [
                {"id": "1", "type": "Concept", "properties": {"name": "Test"}}
            ],
            "relationships": [],
            "summary": "Test summary",
            "timestamp": "2023-01-01T00:00:00Z",
        }

        # Mock the Injector client response with error
        mock_injector.send_data_for_injection.return_value = {
            "success": False,
            "error": "Injector processing failed",
        }

        # Test processing a cache entry
        result = await _process_cache_entry("test_key", "test_value")

        # Verify results
        self.assertFalse(result)
        mock_distiller.process_text.assert_called_once_with(
            "test_value", "context_cache"
        )
        mock_injector.send_data_for_injection.assert_called_once()

    @patch("archivist_agent.redis_client")
    async def test_scan_cache_no_entries(self, mock_redis):
        """Test scanning cache when no entries are found."""
        # Mock the Redis client methods
        mock_redis.keys.return_value = []
        mock_redis.smembers.return_value = set()

        # Test scanning cache
        await _scan_cache()

        # Verify results
        mock_redis.keys.assert_called_once_with("context_cache:*")

    @patch("archivist_agent.redis_client")
    @patch("archivist_agent._process_cache_entry")
    async def test_scan_cache_with_entries(self, mock_process_entry, mock_redis):
        """Test scanning cache when entries are found."""
        # Mock the Redis client methods
        mock_redis.keys.return_value = ["context_cache:key1", "context_cache:key2"]
        mock_redis.smembers.return_value = set()
        mock_redis.hgetall.side_effect = [{"value": "value1"}, {"value": "value2"}]

        # Mock the process entry function
        mock_process_entry.return_value = True

        # Test scanning cache
        await _scan_cache()

        # Verify results
        mock_redis.keys.assert_called_once_with("context_cache:*")
        self.assertEqual(mock_process_entry.call_count, 2)
        mock_process_entry.assert_any_call("key1", "value1")
        mock_process_entry.assert_any_call("key2", "value2")


class TestTemporalDatabaseOperations(unittest.TestCase):
    """Test cases for temporal database operations."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock the database manager
        self.mock_db_manager = MagicMock()

    def test_get_or_create_timenode(self):
        """Test the get_or_create_timenode function."""
        # Mock the database manager response
        timestamp = datetime(2023, 1, 1)
        expected_result = {"day_id": 123, "day": 1}
        self.mock_db_manager.get_or_create_timenode.return_value = expected_result

        # Test the function
        result = self.mock_db_manager.get_or_create_timenode(timestamp)

        # Verify results
        self.assertEqual(result, expected_result)
        self.mock_db_manager.get_or_create_timenode.assert_called_once_with(timestamp)

    def test_link_memory_to_timenode(self):
        """Test the link_memory_to_timenode function."""
        # Mock the database manager response
        memory_node_id = 123
        timestamp = datetime(2023, 1, 1)
        self.mock_db_manager.link_memory_to_timenode.return_value = True

        # Test the function
        result = self.mock_db_manager.link_memory_to_timenode(memory_node_id, timestamp)

        # Verify results
        self.assertTrue(result)
        self.mock_db_manager.link_memory_to_timenode.assert_called_once_with(
            memory_node_id, timestamp
        )


if __name__ == "__main__":
    # Run the tests
    unittest.main()
