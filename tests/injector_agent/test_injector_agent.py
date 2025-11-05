"""
Unit tests for the Injector Agent
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add the project root directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ece.agents.tier3.injector.injector_agent import InjectorAgent


class TestInjectorAgent(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a mock database manager
        self.mock_db_manager = Mock()

        # Create an instance of the injector agent with mock dependencies
        with patch(
            "ece.agents.tier3.injector.injector_agent.Neo4jManager"
        ) as mock_neo4j_manager:
            mock_neo4j_manager.return_value = self.mock_db_manager
            self.injector_agent = InjectorAgent()

    def test_init(self):
        """Test that the injector agent initializes correctly."""
        self.assertIsNotNone(self.injector_agent)

    def test_translate_to_cypher_with_entities(self):
        """Test translating entity data to Cypher queries."""
        data = {
            "entities": [
                {
                    "id": "entity1",
                    "type": "Person",
                    "properties": {"name": "John Doe", "age": 30},
                }
            ]
        }

        queries = self.injector_agent._translate_to_cypher(data)

        # Check that we have the expected number of queries
        self.assertEqual(len(queries), 1)

        # Check the query structure
        query = queries[0]
        self.assertIn("query", query)
        self.assertIn("parameters", query)

        # Check the query content
        self.assertIn("MERGE", query["query"])
        self.assertIn("{label}", query["query"])  # The label is a parameter

        # Check the parameters
        params = query["parameters"]
        self.assertEqual(params["id"], "entity1")
        self.assertEqual(params["label"], "Person")
        self.assertEqual(params["properties"]["name"], "John Doe")
        self.assertEqual(params["properties"]["age"], 30)

    def test_translate_to_cypher_with_relationships(self):
        """Test translating relationship data to Cypher queries."""
        data = {
            "relationships": [
                {
                    "start_id": "entity1",
                    "start_type": "Person",
                    "end_id": "entity2",
                    "end_type": "Company",
                    "type": "WORKS_FOR",
                    "properties": {"since": "2020-01-01"},
                }
            ]
        }

        queries = self.injector_agent._translate_to_cypher(data)

        # Check that we have the expected number of queries
        self.assertEqual(len(queries), 1)

        # Check the query structure
        query = queries[0]
        self.assertIn("query", query)
        self.assertIn("parameters", query)

        # Check the query content
        self.assertIn("MERGE", query["query"])
        self.assertIn("{start_label}", query["query"])  # The labels are parameters
        self.assertIn("{end_label}", query["query"])
        self.assertIn(
            "{rel_type}", query["query"]
        )  # The relationship type is a parameter

        # Check the parameters
        params = query["parameters"]
        self.assertEqual(params["start_id"], "entity1")
        self.assertEqual(params["start_label"], "Person")
        self.assertEqual(params["end_id"], "entity2")
        self.assertEqual(params["end_label"], "Company")
        self.assertEqual(params["rel_type"], "WORKS_FOR")
        self.assertEqual(params["properties"]["since"], "2020-01-01")

    def test_translate_to_cypher_with_entities_and_relationships(self):
        """Test translating both entities and relationships to Cypher queries."""
        data = {
            "entities": [
                {"id": "entity1", "type": "Person", "properties": {"name": "John Doe"}},
                {
                    "id": "entity2",
                    "type": "Company",
                    "properties": {"name": "Acme Corp"},
                },
            ],
            "relationships": [
                {
                    "start_id": "entity1",
                    "start_type": "Person",
                    "end_id": "entity2",
                    "end_type": "Company",
                    "type": "WORKS_FOR",
                    "properties": {"since": "2020-01-01"},
                }
            ],
        }

        queries = self.injector_agent._translate_to_cypher(data)

        # Check that we have the expected number of queries (2 entities + 1 relationship = 3)
        self.assertEqual(len(queries), 3)

    def test_receive_data_for_injection_with_valid_data(self):
        """Test receiving data for injection with valid data."""
        # Mock the database manager's execute_transaction method
        self.injector_agent.db_manager.execute_transaction = Mock(return_value=True)

        data = {
            "entities": [
                {"id": "entity1", "type": "Person", "properties": {"name": "John Doe"}}
            ]
        }

        result = self.injector_agent.receive_data_for_injection(data)

        # Check the result
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Data injected successfully")

        # Verify that the database manager's execute_transaction method was called
        self.injector_agent.db_manager.execute_transaction.assert_called_once()

    def test_receive_data_for_injection_with_empty_data(self):
        """Test receiving data for injection with empty data."""
        data = {}

        result = self.injector_agent.receive_data_for_injection(data)

        # Check the result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "No data provided for injection")

    def test_receive_data_for_injection_with_database_error(self):
        """Test receiving data for injection when a database error occurs."""
        # Mock the database manager's execute_transaction method to raise an exception
        self.injector_agent.db_manager.execute_transaction = Mock(
            side_effect=Exception("Database error")
        )

        data = {
            "entities": [
                {"id": "entity1", "type": "Person", "properties": {"name": "John Doe"}}
            ]
        }

        result = self.injector_agent.receive_data_for_injection(data)

        # Check the result
        self.assertFalse(result["success"])
        self.assertIn("error", result)

        # Verify that the database manager's execute_transaction method was called
        self.injector_agent.db_manager.execute_transaction.assert_called_once()

    def test_receive_data_for_injection_with_invalid_data_type(self):
        """Test receiving data for injection with invalid data type."""
        data = "invalid data"

        result = self.injector_agent.receive_data_for_injection(data)

        # Check the result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid data format provided for injection")

    def test_receive_data_for_injection_with_empty_data(self):
        """Test receiving data for injection with empty data."""
        data = {}

        result = self.injector_agent.receive_data_for_injection(data)

        # Check the result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "No data provided for injection")


if __name__ == "__main__":
    unittest.main()
