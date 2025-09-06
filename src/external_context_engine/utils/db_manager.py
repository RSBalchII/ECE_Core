"""
Database Manager for Neo4j integration in the External Context Engine
"""
from typing import Dict, Any, List, Optional
import logging
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jManager:
    """
    Manager for Neo4j database operations
    """
    
    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize the Neo4jManager.
        
        Args:
            uri: Neo4j database URI
            user: Database username
            password: Database password
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        
    def connect(self):
        """
        Establish connection to Neo4j database.
        """
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            logger.info("Connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j database: {e}")
            raise
            
    def disconnect(self):
        """
        Close connection to Neo4j database.
        """
        if self.driver:
            self.driver.close()
            logger.info("Disconnected from Neo4j database")
            
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query against the Neo4j database.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of records returned by the query
        """
        if not self.driver:
            raise Exception("Database not connected")
            
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
            
    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a node in the Neo4j database.
        
        Args:
            label: Node label
            properties: Node properties
            
        Returns:
            Created node data
        """
        query = f"CREATE (n:{label} $props) RETURN n"
        parameters = {"props": properties}
        result = self.execute_query(query, parameters)
        return result[0] if result else {}
        
    def create_relationship_by_ids(self, start_node_id: str, end_node_id: str, 
                          relationship_type: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a relationship between two nodes using their 'id' properties.
        
        Args:
            start_node_id: ID property of the start node
            end_node_id: ID property of the end node
            relationship_type: Type of relationship
            properties: Relationship properties
            
        Returns:
            Created relationship data
        """
        query = (
            "MATCH (a {id: $start_id}), (b {id: $end_id}) "
            "CREATE (a)-[r:" + relationship_type + " $props]->(b) "
            "RETURN r"
        )
        
        parameters = {
            "start_id": start_node_id,
            "end_id": end_node_id,
            "props": properties or {}
        }
        
        try:
            result = self.execute_query(query, parameters)
            return result[0] if result else {}
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            raise
        
    def create_relationship(self, start_node_id: str, end_node_id: str, 
                          relationship_type: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a relationship between two nodes.
        
        Args:
            start_node_id: ID of the start node
            end_node_id: ID of the end node
            relationship_type: Type of relationship
            properties: Relationship properties
            
        Returns:
            Created relationship data
        """
        query = """
        MATCH (a), (b)
        WHERE id(a) = $start_id AND id(b) = $end_id
        CREATE (a)-[r:{} $props]->(b)
        RETURN r
        """.format(relationship_type)
        
        parameters = {
            "start_id": int(start_node_id),
            "end_id": int(end_node_id),
            "props": properties or {}
        }
        
        result = self.execute_query(query, parameters)
        return result[0] if result else {}
        
    def find_nodes_by_property(self, label: str, property_key: str, property_value: Any) -> List[Dict[str, Any]]:
        """
        Find nodes by property value.
        
        Args:
            label: Node label (can be empty for any label)
            property_key: Property key to search by
            property_value: Property value to match
            
        Returns:
            List of matching nodes
        """
        if label:
            query = f"MATCH (n:{label} {{{property_key}: $value}}) RETURN n"
        else:
            query = f"MATCH (n {{{property_key}: $value}}) RETURN n"
            
        parameters = {"value": property_value}
        return self.execute_query(query, parameters)
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary containing database statistics
        """
        query = """
        MATCH (n)
        OPTIONAL MATCH ()-[r]->()
        RETURN 
            count(n) AS node_count,
            count(r) AS relationship_count
        """
        result = self.execute_query(query)
        return result[0] if result else {}
