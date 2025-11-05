"""
Unit tests for the Neo4jManager in the Injector Agent
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the project root directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ece.agents.tier3.injector.db_manager import Neo4jManager


class TestNeo4jManager(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.neo4j_manager = Neo4jManager(
            uri="bolt://localhost:7688", user="neo4j", password="password"
        )

    def test_init(self):
        """Test that the Neo4jManager initializes correctly."""
        self.assertEqual(self.neo4j_manager.uri, "bolt://localhost:7688")
        self.assertEqual(self.neo4j_manager.user, "neo4j")
        self.assertEqual(self.neo4j_manager.password, "password")
        self.assertIsNone(self.neo4j_manager.driver)

    @patch("ece.agents.tier3.injector.db_manager.GraphDatabase")
    def test_connect(self, mock_graph_database):
        """Test connecting to the Neo4j database."""
        mock_driver = Mock()
        mock_graph_database.driver.return_value = mock_driver

        self.neo4j_manager.connect()

        # Verify that GraphDatabase.driver was called with the correct arguments
        mock_graph_database.driver.assert_called_once_with(
            "bolt://localhost:7688", auth=("neo4j", "password")
        )

        # Verify that the driver was set correctly
        self.assertEqual(self.neo4j_manager.driver, mock_driver)

    def test_disconnect(self):
        """Test disconnecting from the Neo4j database."""
        # First connect to set up the driver
        with patch("ece.agents.tier3.injector.db_manager.GraphDatabase"):
            self.neo4j_manager.connect()

        # Mock the driver's close method
        self.neo4j_manager.driver = Mock()

        self.neo4j_manager.disconnect()

        # Verify that the driver's close method was called
        self.neo4j_manager.driver.close.assert_called_once()

    @patch(
        "ece.agents.tier3.injector.db_manager.time.sleep", return_value=None
    )  # Mock sleep to speed up tests
    def test_execute_query_success(self, mock_sleep):
        """Test executing a query successfully."""
        # Set up the mock driver and session
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_driver.session.return_value = mock_session
        mock_record = Mock()
        mock_record.data.return_value = {"result": "success"}
        mock_session.run.return_value = [mock_record]

        self.neo4j_manager.driver = mock_driver

        result = self.neo4j_manager.execute_query(
            "MATCH (n) RETURN n", {"param": "value"}
        )

        # Verify the result
        self.assertEqual(result, [{"result": "success"}])

        # Verify that the session's run method was called with the correct arguments
        mock_session.run.assert_called_once_with(
            "MATCH (n) RETURN n", {"param": "value"}
        )

    @patch(
        "ece.agents.tier3.injector.db_manager.time.sleep", return_value=None
    )  # Mock sleep to speed up tests
    def test_execute_query_transient_error_retry_success(self, mock_sleep):
        """Test that transient errors are retried and eventually succeed."""
        # Set up the mock driver and session
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_driver.session.return_value = mock_session

        # First call raises a transient error, second call succeeds
        mock_session.run.side_effect = [
            Exception("Connection reset by peer"),
            [Mock(data=Mock(return_value={"result": "success"}))],
        ]

        self.neo4j_manager.driver = mock_driver

        result = self.neo4j_manager.execute_query("MATCH (n) RETURN n")

        # Verify the result
        self.assertEqual(result, [{"result": "success"}])

        # Verify that the session's run method was called twice (retry)
        self.assertEqual(mock_session.run.call_count, 2)

    def test_is_transient_error(self):
        """Test identifying transient errors."""
        # Test transient errors
        self.assertTrue(
            self.neo4j_manager._is_transient_error(
                Exception("Connection reset by peer")
            )
        )
        self.assertTrue(
            self.neo4j_manager._is_transient_error(Exception("Timeout occurred"))
        )
        self.assertTrue(
            self.neo4j_manager._is_transient_error(
                Exception("Database is temporarily unavailable")
            )
        )

        # Test non-transient errors
        self.assertFalse(
            self.neo4j_manager._is_transient_error(Exception("Syntax error"))
        )
        self.assertFalse(
            self.neo4j_manager._is_transient_error(Exception("Constraint violation"))
        )


if __name__ == "__main__":
    unittest.main()
