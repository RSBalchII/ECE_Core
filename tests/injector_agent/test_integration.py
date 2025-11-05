"""
Integration tests for the Injector Agent that connect to a Neo4j database
"""

import unittest
import os
import sys

# Add the project root directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ece.agents.tier3.injector.injector_agent import InjectorAgent


class TestInjectorAgentIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up class fixtures before running tests in the class."""
        # Get Neo4j connection details from environment variables, with defaults for local development
        cls.neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7688")
        cls.neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
        cls.neo4j_password = os.environ.get("NEO4J_PASSWORD", "password")

        # Create an instance of the injector agent
        cls.injector_agent = InjectorAgent(
            neo4j_uri=cls.neo4j_uri,
            neo4j_user=cls.neo4j_user,
            neo4j_password=cls.neo4j_password,
        )

    def test_inject_entities_and_relationships(self):
        """Test injecting entities and relationships."""
        # Test data
        data = {
            "entities": [
                {
                    "id": "test_person_1",
                    "type": "Person",
                    "properties": {"name": "John Doe", "age": 30},
                },
                {
                    "id": "test_company_1",
                    "type": "Company",
                    "properties": {"name": "Acme Corp", "industry": "Technology"},
                },
            ],
            "relationships": [
                {
                    "start_id": "test_person_1",
                    "start_type": "Person",
                    "end_id": "test_company_1",
                    "end_type": "Company",
                    "type": "WORKS_FOR",
                    "properties": {"since": "2020-01-01", "role": "Developer"},
                }
            ],
        }

        # Inject the data
        result = self.injector_agent.receive_data_for_injection(data)

        # Check the result
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Data injected successfully")
        self.assertEqual(result["queries_executed"], 3)  # 2 entities + 1 relationship


if __name__ == "__main__":
    unittest.main()
