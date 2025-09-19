"""
QLearningAgent Implementation

This module implements a Q-Learning algorithm for intelligent graph navigation
in the External Context Engine system. The agent is used by the Archivist to
find optimal paths between concepts in the Neo4j knowledge graph.
"""

import asyncio
import logging
import random
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GraphState:
    """Represents a state in the knowledge graph"""
    node_id: str
    node_name: str
    node_type: str = "Concept"
    features: Dict[str, Any] = None


@dataclass
class Action:
    """Represents an action (edge traversal) in the graph"""
    from_node: str
    to_node: str
    relationship_type: str
    weight: float = 1.0


class MemoryPath(BaseModel):
    """Represents a path through the knowledge graph"""
    nodes: List[str] = Field(default_factory=list, description="Node names in the path")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Relationships in the path")
    score: float = Field(default=0.0, description="Path relevance score")
    length: int = Field(default=0, description="Path length (number of hops)")


class QLearningGraphAgent:
    """
    Q-Learning agent for intelligent navigation of the Neo4j knowledge graph.
    
    This agent is used by the Archivist to find optimal paths between concepts
    using a Reinforcement Learning approach.
    """
    
    def __init__(self, graph_manager=None, config=None):
        """
        Initialize the QLearningGraphAgent.
        
        Args:
            graph_manager: Manager for interacting with the Neo4j database
            config: Configuration parameters for the agent
        """
        self.graph_manager = graph_manager
        self.config = config or {}
        self.q_table = {}  # In-memory Q-table for state-action values
        self.learning_rate = self.config.get('learning_rate', 0.1)
        self.discount_factor = self.config.get('discount_factor', 0.9)
        self.epsilon = self.config.get('epsilon', 0.1)  # For epsilon-greedy exploration
        self.is_training = False
        self.training_task = None  # Background training task
        self.training_interval = self.config.get('training_interval', 300)  # 5 minutes default
        
        # Connect to the graph manager if provided
        if self.graph_manager:
            try:
                self.graph_manager.connect()
            except Exception as e:
                logger.error(f"Failed to connect to graph manager: {e}")
        
    async def find_optimal_path(self, keywords: List[str]) -> List[MemoryPath]:
        """
        Find optimal paths related to a list of keywords.

        Args:
            keywords: A list of keywords to search for.
            
        Returns:
            List of MemoryPath objects ranked by Q-values
        """
        logger.info(f"Finding optimal paths for keywords: {keywords}")
        
        if not self.graph_manager:
            logger.warning("No graph manager available")
            return []

        # Find nodes related to the keywords
        nodes = await self.graph_manager.find_nodes_by_keywords(keywords)
        
        if not nodes:
            logger.info("No nodes found for the given keywords.")
            return []

        # For simplicity, find paths between all pairs of found nodes
        paths = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                start_node = nodes[i]['id']
                end_node = nodes[j]['id']
                path = await self._q_learning_pathfinding(start_node, end_node)
                if path:
                    paths.append(path)
        
        return paths
        
    async def update_q_values(self, path: MemoryPath, reward: float) -> None:
        """
        Update Q-values based on the path taken and reward received.
        
        Args:
            path: The path that was taken
            reward: The reward received for taking this path
        """
        logger.info(f"Updating Q-values for path with reward {reward}")
        
        if len(path.nodes) < 2:
            logger.warning("Path too short to update Q-values")
            return
            
        # Update Q-values for each state-action pair in the path
        for i in range(len(path.nodes) - 1):
            state = path.nodes[i]
            next_state = path.nodes[i + 1]
            
            # Find the relationship to get the action
            action = None
            for rel in path.relationships:
                if rel.get('start_node') == state and rel.get('end_node') == next_state:
                    action = f"{next_state}:{rel.get('type', 'RELATED_TO')}"
                    break
                    
            if action:
                # Get current Q-value
                current_q = self._get_q_value(state, action)
                
                # Calculate max Q-value for next state
                max_next_q = self._get_max_q_value(next_state)
                
                # Apply Q-learning update rule
                new_q = current_q + self.learning_rate * (reward + self.discount_factor * max_next_q - current_q)
                
                # Update Q-table
                self._set_q_value(state, action, new_q)
                
                logger.debug(f"Updated Q-value for {state}->{action}: {current_q} -> {new_q}")
        
    async def train(self, training_data: List[Tuple[str, str, float]]) -> None:
        """
        Train the agent with historical path data.
        
        Args:
            training_data: List of (start_node, end_node, reward) tuples
        """
        logger.info(f"Training with {len(training_data)} data points")
        
        self.is_training = True
        try:
            for start_node, end_node, reward in training_data:
                # Find path using current policy
                path = await self._q_learning_pathfinding(start_node, end_node)
                if path:
                    # Update Q-values based on reward
                    await self.update_q_values(path, reward)
        finally:
            self.is_training = False
        
    async def start_continuous_training(self) -> None:
        """
        Start the continuous training loop as a background task.
        """
        if self.training_task and not self.training_task.done():
            logger.warning("Training task is already running")
            return
            
        self.training_task = asyncio.create_task(self._continuous_training_loop())
        logger.info("Started continuous training loop")
        
    async def stop_continuous_training(self) -> None:
        """
        Stop the continuous training loop.
        """
        if self.training_task and not self.training_task.done():
            self.training_task.cancel()
            try:
                await self.training_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped continuous training loop")
            
    async def _continuous_training_loop(self) -> None:
        """
        Background loop for continuous training.
        """
        logger.info("Continuous training loop started")
        
        while True:
            try:
                # Perform continuous training
                await self._perform_continuous_training()
                
                # Wait for the next training interval
                await asyncio.sleep(self.training_interval)
            except asyncio.CancelledError:
                logger.info("Continuous training loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in continuous training loop: {e}")
                # Wait before retrying
                await asyncio.sleep(60)
                
    async def _perform_continuous_training(self) -> None:
        """
        Perform one iteration of continuous training by exploring the graph.
        """
        logger.info("Performing continuous training iteration")
        
        if not self.graph_manager:
            logger.warning("No graph manager available for continuous training")
            return
            
        # Get a random node to start exploration
        start_node = await self._get_random_node()
        if not start_node:
            logger.warning("No nodes available for continuous training")
            return
            
        # Explore from this node to learn more about the graph
        await self._explore_from_node(start_node)
        
        # Synchronize Q-values to the graph
        await self.sync_q_values_to_graph()
        
    async def _get_random_node(self) -> Optional[str]:
        """
        Get a random node ID from the graph for exploration.
        
        Returns:
            A random node ID or None if no nodes found
        """
        # This is a simplified implementation
        # In a real implementation, you might query the database for a random node
        if self.q_table:
            # Return a random node from our Q-table
            return random.choice(list(self.q_table.keys()))
        return None
        
    async def _explore_from_node(self, start_node: str, max_steps: int = 10) -> None:
        """
        Explore the graph from a starting node to learn Q-values.
        
        Args:
            start_node: The node ID to start exploration from
            max_steps: Maximum number of steps to take during exploration
        """
        logger.debug(f"Exploring from node {start_node}")
        
        current_node = start_node
        path = MemoryPath(nodes=[start_node])
        
        for step in range(max_steps):
            # Get possible actions from current node
            actions = await self._query_graph_structure(current_node)
            
            if not actions:
                logger.debug(f"No actions available from node {current_node}")
                break
                
            # Choose a random action for exploration
            action = random.choice(actions)
            
            # Add action to path
            path.nodes.append(action.to_node)
            path.relationships.append({
                "start_node": action.from_node,
                "end_node": action.to_node,
                "type": action.relationship_type
            })
            path.length += 1
            
            # Move to next node
            current_node = action.to_node
            
        # Update Q-values based on exploration (using a default reward)
        # In a real implementation, this reward would be based on some metric
        await self.update_q_values(path, reward=0.1)
        
    async def sync_q_values_to_graph(self) -> None:
        """
        Synchronize in-memory Q-values with Neo4j relationship properties.
        """
        logger.info("Synchronizing Q-values to graph")
        
        if self.graph_manager:
            try:
                self.graph_manager.sync_q_values_to_graph(self.q_table)
                logger.info("Successfully synchronized Q-values to graph")
            except Exception as e:
                logger.error(f"Failed to synchronize Q-values to graph: {e}")
        else:
            logger.warning("No graph manager available for synchronization")
            
    def get_convergence_metrics(self) -> Dict[str, Any]:
        """
        Get convergence metrics for monitoring the Q-Learning process.
        
        Returns:
            Dictionary containing convergence metrics
        """
        if not self.q_table:
            return {
                "q_table_size": 0,
                "total_q_values": 0,
                "average_q_value": 0.0,
                "max_q_value": 0.0,
                "min_q_value": 0.0
            }
            
        total_q_values = 0
        sum_q_values = 0.0
        max_q_value = float('-inf')
        min_q_value = float('inf')
        
        for state_actions in self.q_table.values():
            for q_value in state_actions.values():
                total_q_values += 1
                sum_q_values += q_value
                max_q_value = max(max_q_value, q_value)
                min_q_value = min(min_q_value, q_value)
                
        return {
            "q_table_size": len(self.q_table),
            "total_q_values": total_q_values,
            "average_q_value": sum_q_values / total_q_values if total_q_values > 0 else 0.0,
            "max_q_value": max_q_value if max_q_value != float('-inf') else 0.0,
            "min_q_value": min_q_value if min_q_value != float('inf') else 0.0
        }
        
    async def _query_graph_structure(self, node_id: str) -> List[Action]:
        """
        Query the graph to get possible actions from a given node.
        
        Args:
            node_id: The node ID to query
            
        Returns:
            List of possible actions from this node
        """
        logger.debug(f"Querying graph structure for node {node_id}")
        
        if not self.graph_manager:
            logger.warning("No graph manager available")
            return []
            
        try:
            neighbors = self.graph_manager.get_neighbors(node_id)
            actions = []
            
            for neighbor in neighbors:
                action = Action(
                    from_node=node_id,
                    to_node=neighbor["to_node"],
                    relationship_type=neighbor["relationship_type"],
                    weight=1.0  # Could be enhanced with relationship properties
                )
                actions.append(action)
                
            return actions
        except Exception as e:
            logger.error(f"Failed to query graph structure: {e}")
            return []
            
    async def _q_learning_pathfinding(self, start_node: str, end_node: str, max_steps: int = 20) -> MemoryPath:
        """
        Use Q-learning to find a path from start to end node.
        
        Args:
            start_node: The starting node ID
            end_node: The target node ID
            max_steps: Maximum number of steps to take
            
        Returns:
            MemoryPath representing the found path
        """
        current_node = start_node
        path = MemoryPath(nodes=[start_node])
        visited = {start_node}
        
        for step in range(max_steps):
            # Check if we've reached the target
            if current_node == end_node:
                path.score = 1.0  # Perfect score for reaching target
                return path
                
            # Get possible actions from current node
            actions = await self._query_graph_structure(current_node)
            
            if not actions:
                logger.debug(f"No actions available from node {current_node}")
                break
                
            # Choose action using epsilon-greedy policy
            if random.random() < self.epsilon and not self.is_training:
                # Explore: choose random action
                action = random.choice(actions)
                logger.debug(f"Exploring: randomly chose action {action.to_node}")
            else:
                # Exploit: choose best action based on Q-values
                best_action = None
                best_q_value = float('-inf')
                
                for action in actions:
                    action_key = f"{action.to_node}:{action.relationship_type}"
                    q_value = self._get_q_value(current_node, action_key)
                    
                    if q_value > best_q_value:
                        best_q_value = q_value
                        best_action = action
                        
                action = best_action
                logger.debug(f"Exploiting: chose best action {action.to_node} with Q-value {best_q_value}")
                
            # Add action to path
            path.nodes.append(action.to_node)
            path.relationships.append({
                "start_node": action.from_node,
                "end_node": action.to_node,
                "type": action.relationship_type
            })
            path.length += 1
            
            # Move to next node
            current_node = action.to_node
            
            # Check for cycles
            if current_node in visited:
                logger.debug(f"Detected cycle at node {current_node}")
                break
            visited.add(current_node)
            
        # If we didn't reach the target, calculate partial score
        path.score = self._calculate_path_score(path, end_node)
        return path
        
    def _get_q_value(self, state: str, action: str) -> float:
        """
        Get Q-value for a state-action pair.
        
        Args:
            state: The state (node ID)
            action: The action (to_node:relationship_type)
            
        Returns:
            Q-value for the state-action pair
        """
        if state in self.q_table and action in self.q_table[state]:
            return self.q_table[state][action]
        return 0.0  # Default Q-value
        
    def _set_q_value(self, state: str, action: str, value: float) -> None:
        """
        Set Q-value for a state-action pair.
        
        Args:
            state: The state (node ID)
            action: The action (to_node:relationship_type)
            value: The Q-value to set
        """
        if state not in self.q_table:
            self.q_table[state] = {}
        self.q_table[state][action] = value
        
    def _get_max_q_value(self, state: str) -> float:
        """
        Get maximum Q-value for all actions from a state.
        
        Args:
            state: The state (node ID)
            
        Returns:
            Maximum Q-value for all actions from this state
        """
        if state in self.q_table:
            if self.q_table[state]:
                return max(self.q_table[state].values())
        return 0.0  # Default when no actions or no Q-values
        
    def _calculate_path_score(self, path: MemoryPath, target_node: str) -> float:
        """
        Calculate a score for a path based on how close it gets to the target.
        
        Args:
            path: The path to score
            target_node: The target node ID
            
        Returns:
            Score for the path (0.0 to 1.0)
        """
        if not path.nodes:
            return 0.0
            
        # Perfect score for reaching target
        if path.nodes[-1] == target_node:
            return 1.0
            
        # Partial score based on path length (shorter is better)
        # This is a simple heuristic - could be enhanced with graph distance metrics
        max_reasonable_length = 10  # Assumption about reasonable path length
        length_score = max(0.0, 1.0 - (path.length / max_reasonable_length))
        
        return length_score * 0.5  # Max 0.5 for non-target paths

    async def refine_relationships(self, path: MemoryPath, reward: float):
        """Refine relationships in the graph based on a path and a reward."""
        logger.info(f"Refining relationships for path with reward {reward}")
        await self.update_q_values(path, reward)
