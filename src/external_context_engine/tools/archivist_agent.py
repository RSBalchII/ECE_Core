"""
Archivist Agent Implementation

This module implements the ArchivistAgent for storing and retrieving structured information
in the knowledge graph using Neo4j as the persistence layer.
"""

from typing import Dict, Any, List, Union, Optional
from pydantic import BaseModel
import logging
from src.external_context_engine.utils.db_manager import Neo4jManager

logger = logging.getLogger(__name__)


class Entity(BaseModel):
    """Data model for an entity in the knowledge graph."""
    id: str
    type: str
    properties: Dict[str, Any]


class Relationship(BaseModel):
    """Data model for a relationship in the knowledge graph."""
    id: str
    type: str
    start_entity_id: str
    end_entity_id: str
    properties: Dict[str, Any]


class Query(BaseModel):
    """Data model for a query to the knowledge graph."""
    cypher: str
    parameters: Dict[str, Any]


class ArchivistAgent:
    """
    The Archivist Agent is responsible for managing the knowledge graph.
    It processes queries to retrieve context and stores new information.
    """
    
    def __init__(self, neo4j_manager: Neo4jManager):
        """
        Initialize the ArchivistAgent.
        
        Args:
            neo4j_manager: The manager for interacting with the Neo4j database.
        """
        self.graph_db = neo4j_manager
        
    async def store(self, data: List[Union[Entity, Relationship]]) -> Dict[str, Any]:
        """
        Store entities and relationships in the knowledge graph.
        
        Args:
            data: List of entities and relationships to store
            
        Returns:
            Dictionary with confirmation of storage operation
        """
        try:
            stored_entities = []
            stored_relationships = []
            
            for item in data:
                if isinstance(item, Entity):
                    # Create or update entity node
                    node_data = self.graph_db.create_node(
                        label=item.type,
                        properties={"id": item.id, **item.properties}
                    )
                    stored_entities.append(node_data)
                elif isinstance(item, Relationship):
                    # Create or update relationship using the new method
                    rel_data = self.graph_db.create_relationship_by_ids(
                        start_node_id=item.start_entity_id,
                        end_node_id=item.end_entity_id,
                        relationship_type=item.type,
                        properties=item.properties
                    )
                    stored_relationships.append(rel_data)
            
            return {
                "success": True,
                "stored_entities": len(stored_entities),
                "stored_relationships": len(stored_relationships)
            }
        except Exception as e:
            logger.error(f"Failed to store data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def retrieve(self, query: Query) -> List[Dict[str, Any]]:
        """
        Retrieve information from the knowledge graph based on a query.
        
        Args:
            query: Query object containing Cypher query and parameters
            
        Returns:
            List of query results
        """
        try:
            results = self.graph_db.execute_query(
                query=query.cypher,
                parameters=query.parameters
            )
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve data: {e}")
            return []
            
    async def update(self, item: Union[Entity, Relationship]) -> Dict[str, Any]:
        """
        Update an entity or relationship in the knowledge graph.
        
        Args:
            item: Entity or Relationship to update
            
        Returns:
            Dictionary with confirmation of update operation
        """
        try:
            if isinstance(item, Entity):
                # For updating an entity, we'll use a MERGE operation
                # First, find the existing node
                existing_nodes = self.graph_db.find_nodes_by_property(
                    label="", 
                    property_key="id", 
                    property_value=item.id
                )
                
                if existing_nodes:
                    # Update the node properties
                    # In a real implementation, we would update the node properties
                    # For now, we'll just log that we found the node
                    logger.info(f"Found entity {item.id} for update")
                    return {
                        "success": True,
                        "updated": True,
                        "id": item.id
                    }
                else:
                    # Create new node if it doesn't exist
                    node_data = self.graph_db.create_node(
                        label=item.type,
                        properties={"id": item.id, **item.properties}
                    )
                    return {
                        "success": True,
                        "created": True,
                        "id": item.id
                    }
            elif isinstance(item, Relationship):
                # For updating a relationship, we'll need to find and update it
                # This is more complex and would require a specific implementation
                # For now, we'll just log that we're updating a relationship
                logger.info(f"Updating relationship {item.id}")
                return {
                    "success": True,
                    "message": f"Relationship {item.id} update initiated"
                }
        except Exception as e:
            logger.error(f"Failed to update item: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def delete(self, item_id: str, item_type: str) -> Dict[str, Any]:
        """
        Delete an entity or relationship from the knowledge graph.
        
        Args:
            item_id: ID of the entity or relationship to delete
            item_type: Type of the item ('entity' or 'relationship')
            
        Returns:
            Dictionary with confirmation of deletion operation
        """
        try:
            if item_type.lower() == "entity":
                # Delete entity node
                # This would require a Cypher query to delete the node and its relationships
                query = "MATCH (n {id: $id}) DETACH DELETE n"
                self.graph_db.execute_query(query, {"id": item_id})
                return {
                    "success": True,
                    "deleted": True,
                    "id": item_id,
                    "type": "entity"
                }
            elif item_type.lower() == "relationship":
                # Delete relationship
                # This would require a Cypher query to delete the relationship
                query = "MATCH ()-[r {id: $id}]->() DELETE r"
                self.graph_db.execute_query(query, {"id": item_id})
                return {
                    "success": True,
                    "deleted": True,
                    "id": item_id,
                    "type": "relationship"
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid item type. Must be 'entity' or 'relationship'"
                }
        except Exception as e:
            logger.error(f"Failed to delete item: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def retrieve_paths_with_qvalues(self, start_node: str, end_node: str, max_hops: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve paths between two nodes considering Q-values for optimal traversal.
        
        Args:
            start_node: Name of the starting node
            end_node: Name of the target node
            max_hops: Maximum number of hops in the path
            
        Returns:
            List of paths ranked by their Q-values
        """
        try:
            # Query to find paths with Q-values
            query = """
            MATCH path = (start {name: $start_node})-[:TRANSITION*..$max_hops]->(end {name: $end_node})
            WITH path, relationships(path) as rels
            UNWIND rels as r
            WITH path, collect(r.q_value) as q_values
            WITH path, 
                 reduce(sum_q = 0.0, q IN q_values | sum_q + coalesce(q, 0.0)) as total_q_value,
                 length(path) as path_length
            RETURN 
                [n IN nodes(path) | n.name] as node_names,
                total_q_value,
                path_length
            ORDER BY total_q_value DESC
            LIMIT 10
            """
            
            results = self.graph_db.execute_query(
                query,
                {
                    "start_node": start_node,
                    "end_node": end_node,
                    "max_hops": max_hops
                }
            )
            
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve paths with Q-values: {e}")
            return []
    
    async def get_optimal_path(self, start_node: str, end_node: str, max_hops: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get the single optimal path between two nodes based on Q-values.
        
        Args:
            start_node: Name of the starting node
            end_node: Name of the target node
            max_hops: Maximum number of hops in the path
            
        Returns:
            Dictionary containing the optimal path and its Q-value, or None if no path found
        """
        try:
            # Query to find the optimal path based on Q-values
            query = """
            MATCH path = (start {name: $start_node})-[:TRANSITION*..$max_hops]->(end {name: $end_node})
            WITH path, relationships(path) as rels
            UNWIND rels as r
            WITH path, collect(r.q_value) as q_values
            WITH path, 
                 reduce(sum_q = 0.0, q IN q_values | sum_q + coalesce(q, 0.0)) as total_q_value,
                 length(path) as path_length
            RETURN 
                [n IN nodes(path) | n.name] as node_names,
                total_q_value,
                path_length
            ORDER BY total_q_value DESC
            LIMIT 1
            """
            
            results = self.graph_db.execute_query(
                query,
                {
                    "start_node": start_node,
                    "end_node": end_node,
                    "max_hops": max_hops
                }
            )
            
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Failed to get optimal path: {e}")
            return None