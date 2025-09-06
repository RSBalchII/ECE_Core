"""
Integration tests for the ArchivistAgent with a real Neo4j database
"""

import unittest
import asyncio
from src.external_context_engine.tools.archivist_agent import ArchivistAgent, Entity, Relationship, Query
from src.external_context_engine.utils.db_manager import Neo4jManager


class TestArchivistAgentIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Initialize the Neo4jManager with test database credentials
        self.neo4j_manager = Neo4jManager(
            uri="bolt://localhost:7688",
            user="neo4j",
            password="password"
        )
        
        # Connect to the database
        self.neo4j_manager.connect()
        
        # Clear the database before each test
        self.neo4j_manager.execute_query("MATCH (n) DETACH DELETE n")
        
        # Initialize the ArchivistAgent
        self.agent = ArchivistAgent(neo4j_manager=self.neo4j_manager)
        
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Clear the database after each test
        self.neo4j_manager.execute_query("MATCH (n) DETACH DELETE n")
        
        # Disconnect from the database
        self.neo4j_manager.disconnect()
        
    def test_store_and_retrieve_entities(self):
        """Test storing and retrieving entities in the knowledge graph."""
        # Create test entities
        entities = [
            Entity(id="1", type="Person", properties={"name": "John Doe", "age": 30}),
            Entity(id="2", type="Organization", properties={"name": "ACME Corp", "industry": "Technology"})
        ]
        
        # Store the entities
        store_result = asyncio.run(self.agent.store(entities))
        
        # Verify the store result
        self.assertTrue(store_result["success"])
        self.assertEqual(store_result["stored_entities"], 2)
        
        # Retrieve the entities
        query = Query(
            cypher="MATCH (p:Person {id: $id}) RETURN p.name, p.age",
            parameters={"id": "1"}
        )
        retrieve_result = asyncio.run(self.agent.retrieve(query))
        
        # Verify the retrieve result
        self.assertEqual(len(retrieve_result), 1)
        self.assertEqual(retrieve_result[0]["p.name"], "John Doe")
        self.assertEqual(retrieve_result[0]["p.age"], 30)
        
    def test_store_and_retrieve_relationships(self):
        """Test storing and retrieving relationships in the knowledge graph."""
        # Create test entities first
        entities = [
            Entity(id="1", type="Person", properties={"name": "John Doe"}),
            Entity(id="2", type="Organization", properties={"name": "ACME Corp"})
        ]
        
        # Store the entities
        asyncio.run(self.agent.store(entities))
        
        # Create test relationship
        relationships = [
            Relationship(
                id="1", 
                type="WORKS_FOR", 
                start_entity_id="1", 
                end_entity_id="2", 
                properties={"since": "2020"}
            )
        ]
        
        # Store the relationships
        store_result = asyncio.run(self.agent.store(relationships))
        
        # Verify the store result
        self.assertTrue(store_result["success"])
        self.assertEqual(store_result["stored_relationships"], 1)
        
        # Retrieve the relationship
        query = Query(
            cypher="""
            MATCH (p:Person {id: $person_id})-[r:WORKS_FOR]->(o:Organization {id: $org_id})
            RETURN p.name, o.name, r.since
            """,
            parameters={"person_id": "1", "org_id": "2"}
        )
        retrieve_result = asyncio.run(self.agent.retrieve(query))
        
        # Verify the retrieve result
        self.assertEqual(len(retrieve_result), 1)
        self.assertEqual(retrieve_result[0]["p.name"], "John Doe")
        self.assertEqual(retrieve_result[0]["o.name"], "ACME Corp")
        self.assertEqual(retrieve_result[0]["r.since"], "2020")


if __name__ == '__main__':
    unittest.main()