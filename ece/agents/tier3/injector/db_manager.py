"""
Database Manager for Neo4j integration in the Injector Agent
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from neo4j import GraphDatabase
import time
import random

logger = logging.getLogger(__name__)


class Neo4jManager:
    """
    Manager for Neo4j database operations specific to the Injector agent
    """
    
    def __init__(self, uri: str, user: str, password: str, max_retries: int = 3):
        """
        Initialize the Neo4jManager.
        
        Args:
            uri: Neo4j database URI
            user: Database username
            password: Database password
            max_retries: Maximum number of retry attempts for transient errors
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.max_retries = max_retries
        self.driver = None
        logger.info(f"Neo4jManager initialized with URI: {uri}")
        
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
        Execute a Cypher query against the Neo4j database with retry logic.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of records returned by the query
        """
        if not self.driver:
            raise Exception("Database not connected")
            
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                with self.driver.session() as session:
                    logger.debug(f"Executing query: {query[:100]}...")  # Log first 100 chars of query
                    if parameters:
                        logger.debug(f"Query parameters: {parameters}")
                    result = session.run(query, parameters or {})
                    return [record.data() for record in result]
            except Exception as e:
                last_exception = e
                # Check if this is a transient error that we should retry
                if self._is_transient_error(e) and attempt < self.max_retries:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Transient error occurred: {e}. Retrying in {wait_time:.2f} seconds (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to execute query after {attempt} attempts: {e}")
                    logger.error(f"Query: {query}")
                    logger.error(f"Parameters: {parameters}")
                    raise
                    
        # If we've exhausted all retries, raise the last exception
        raise last_exception
        
    def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """
        Execute multiple Cypher queries within a single transaction with retry logic.
        
        Args:
            queries: List of dictionaries containing 'query' and 'parameters' keys
            
        Returns:
            True if transaction was successful, False otherwise
        """
        if not self.driver:
            raise Exception("Database not connected")
            
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                with self.driver.session() as session:
                    tx = session.begin_transaction()
                    try:
                        logger.info(f"Starting transaction with {len(queries)} queries")
                        for i, query_dict in enumerate(queries):
                            query = query_dict.get('query')
                            parameters = query_dict.get('parameters', {})
                            logger.debug(f"Executing query {i+1}/{len(queries)}: {query[:100]}...")  # Log first 100 chars
                            tx.run(query, parameters)
                        tx.commit()
                        logger.info(f"Transaction committed successfully with {len(queries)} queries")
                        return True
                    except Exception as e:
                        tx.rollback()
                        logger.error(f"Transaction failed and was rolled back: {e}")
                        raise
            except Exception as e:
                last_exception = e
                # Check if this is a transient error that we should retry
                if self._is_transient_error(e) and attempt < self.max_retries:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Transient error occurred: {e}. Retrying in {wait_time:.2f} seconds (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to execute transaction after {attempt} attempts: {e}")
                    raise
                    
        # If we've exhausted all retries, raise the last exception
        raise last_exception
        
    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and should be retried.
        
        Args:
            error: The exception to check
            
        Returns:
            True if the error is transient, False otherwise
        """
        error_str = str(error).lower()
        
        # Common transient error patterns
        transient_patterns = [
            "connection reset",
            "connection refused",
            "timeout",
            "temporarily unavailable",
            "locked",
            "busy",
            "network"
        ]
        
        is_transient = any(pattern in error_str for pattern in transient_patterns)
        if is_transient:
            logger.debug(f"Identified transient error: {error}")
        return is_transient
        
    def get_or_create_timenode(self, timestamp: datetime) -> Dict[str, Any]:
        """
        Create a chronological tree of nodes: (Year)->[:HAS_MONTH]->(Month)->[:HAS_DAY]->(Day).
        
        Args:
            timestamp: The timestamp to create the chronological tree for
            
        Returns:
            Dictionary containing the day node information
        """
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day
        
        # Create queries for the chronological tree
        queries = [
            {
                'query': """
                    MERGE (y:Year {value: $year})
                    ON CREATE SET y.created_at = timestamp()
                    RETURN y.value as year
                """,
                'parameters': {'year': year}
            },
            {
                'query': """
                    MERGE (year_node:Year {value: $year})
                    MERGE (month_node:Month {value: $month, year: $year})
                    ON CREATE SET month_node.created_at = timestamp()
                    MERGE (year_node)-[:HAS_MONTH]->(month_node)
                    RETURN month_node.value as month
                """,
                'parameters': {'year': year, 'month': month}
            },
            {
                'query': """
                    MERGE (month_node:Month {value: $month, year: $year})
                    MERGE (day_node:Day {value: $day, month: $month, year: $year})
                    ON CREATE SET day_node.created_at = timestamp(), day_node.timestamp = $timestamp
                    MERGE (month_node)-[:HAS_DAY]->(day_node)
                    RETURN day_node.value as day, id(day_node) as day_id
                """,
                'parameters': {
                    'year': year, 
                    'month': month, 
                    'day': day, 
                    'timestamp': timestamp.isoformat()
                }
            }
        ]
        
        # Execute the transaction
        if self.execute_transaction(queries):
            # Retrieve the day node information
            query = """
                MATCH (day_node:Day {value: $day, month: $month, year: $year})
                RETURN day_node.value as day, id(day_node) as day_id
            """
            parameters = {'year': year, 'month': month, 'day': day}
            result = self.execute_query(query, parameters)
            
            if result:
                return result[0]
            else:
                raise Exception("Failed to retrieve day node after creation")
        else:
            raise Exception("Failed to create chronological tree")
            
    def link_memory_to_timenode(self, memory_node_id: int, timestamp: datetime) -> bool:
        """
        Create a [:OCCURRED_AT] relationship to the appropriate Day node.
        
        Args:
            memory_node_id: The ID of the memory node to link
            timestamp: The timestamp to link the memory to
            
        Returns:
            True if the relationship was created successfully, False otherwise
        """
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day
        
        query = """
            MATCH (memory_node)
            WHERE id(memory_node) = $memory_node_id
            MATCH (day_node:Day {value: $day, month: $month, year: $year})
            MERGE (memory_node)-[:OCCURRED_AT]->(day_node)
            RETURN count(*) > 0 as linked
        """
        
        parameters = {
            'memory_node_id': memory_node_id,
            'year': year,
            'month': month,
            'day': day
        }
        
        result = self.execute_query(query, parameters)
        
        if result:
            return result[0].get('linked', False)
        else:
            return False
            
    def _translate_to_cypher(self, data: dict) -> List[Dict[str, Any]]:
        """
        Translate structured JSON data into valid Cypher MERGE queries.
        
        Args:
            data (dict): Structured data to be translated.
            
        Returns:
            List[Dict[str, Any]]: List of dictionaries containing 'query' and 'parameters' keys.
        """
        queries = []
        
        # Handle entities (nodes)
        if 'entities' in data:
            logger.debug(f"Processing {len(data['entities'])} entities")
            for entity in data['entities']:
                label = entity.get('type', 'Entity')
                # Create MERGE query for each entity
                # Using ON CREATE and ON MATCH to handle both new and existing nodes
                query = f"""
                MERGE (n:{label} {{id: $id}})
                ON CREATE SET n += $properties, n.created = timestamp(), n.poml_metadata = $poml_metadata
                ON MATCH SET n += $properties, n.last_updated = timestamp(), n.poml_metadata = $poml_metadata
                """
                parameters = {
                    "id": entity.get('id'),
                    "properties": entity.get('properties', {}),
                    "poml_metadata": data.get('poml_metadata', '')
                }
                queries.append({
                    "query": query.strip(),
                    "parameters": parameters
                })
        
        # Handle relationships
        if 'relationships' in data:
            logger.debug(f"Processing {len(data['relationships'])} relationships")
            for relationship in data['relationships']:
                start_label = relationship.get('start_type', 'Entity')
                end_label = relationship.get('end_type', 'Entity')
                rel_type = relationship.get('type', 'RELATIONSHIP')
                # Create MERGE query for each relationship
                # Using ON CREATE and ON MATCH to handle both new and existing relationships
                query = f"""
                MERGE (a:{start_label} {{id: $start_id}})
                MERGE (b:{end_label} {{id: $end_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                ON CREATE SET r += $properties, r.created = timestamp(), r.poml_metadata = $poml_metadata
                ON MATCH SET r += $properties, r.last_updated = timestamp(), r.poml_metadata = $poml_metadata
                """
                parameters = {
                    "start_id": relationship.get('start_id'),
                    "end_id": relationship.get('end_id'),
                    "properties": relationship.get('properties', {}),
                    "poml_metadata": data.get('poml_metadata', '')
                }
                queries.append({
                    "query": query.strip(),
                    "parameters": parameters
                })
        
        logger.debug(f"Generated {len(queries)} Cypher queries")
        return queries
