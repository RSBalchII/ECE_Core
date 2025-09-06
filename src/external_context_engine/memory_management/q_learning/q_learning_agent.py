# TASK-016: Create Q-Learning Agent class
# TASK-017: Implement Q-Table management
# TASK-018: Develop graph traversal algorithms
# TASK-019: Create training pipeline
# TASK-020: Add Q-Table update mechanism
# TASK-021: Implement path optimization
"""
Q-Learning Agent Implementation

This agent uses reinforcement learning to optimize path finding through the knowledge graph,
learning from successful queries to improve future traversal efficiency.
"""

import asyncio
import logging
import random
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict
import numpy as np

from ..models.memory_path import MemoryPath


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


class QLearningGraphAgent:
    """
    Q-Learning agent for optimal path finding in the knowledge graph.
    
    Uses reinforcement learning to learn the best paths between concepts,
    improving query efficiency over time.
    """
    
    def __init__(self, graph_manager, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Q-Learning Graph Agent.
        
        Args:
            graph_manager: Neo4j graph manager for database operations
            config: Configuration dictionary
        """
        self.graph = graph_manager
        self.config = config or {}
        
        # Q-Learning parameters
        self.learning_rate = self.config.get("learning_rate", 0.1)
        self.discount_factor = self.config.get("discount_factor", 0.9)
        self.epsilon = self.config.get("epsilon", 0.1)  # Exploration rate
        self.max_episodes = self.config.get("max_episodes", 1000)
        
        # Q-Table implementation
        self.q_table = QTable(
            persist_path=self.config.get("q_table_path", "./data/q_table.npy")
        )
        
        # Episode tracking
        self.episode_count = 0
        self.total_rewards = []
        
        # Path cache for efficiency
        self.path_cache = {}
        
        logger.info(f"Q-Learning Agent initialized with α={self.learning_rate}, γ={self.discount_factor}, ε={self.epsilon}")
    
    async def initialize(self):
        """
        Initialize the Q-Learning agent asynchronously.
        This method should be called after creating the agent to load the Q-table
        and initialize Q-values from the Neo4j graph.
        """
        await self.q_table.load()
        await self._initialize_q_table_from_graph()
    
    async def _initialize_q_table_from_graph(self):
        """
        Initialize the in-memory Q-table with Q-values from the Neo4j graph.
        This ensures that the agent starts with any previously learned knowledge.
        """
        logger.info("Initializing Q-table from Neo4j graph...")
        
        query = """
        MATCH (from)-[r:TRANSITION]->(to)
        WHERE exists(r.q_value)
        RETURN from.name as from_node, to.name as to_node, r.q_value as q_value
        """
        
        try:
            results = await asyncio.to_thread(
                self.graph.execute_query,
                query
            )
            
            for record in results:
                from_node = record["from_node"]
                to_node = record["to_node"]
                q_value = record["q_value"]
                
                # Create state and action keys
                state_key = self._get_state_key(from_node)
                action_key = self._get_action_key({"from": from_node, "to": to_node})
                
                # Update Q-table
                self.q_table.update(state_key, action_key, q_value)
            
            logger.info(f"Initialized Q-table with {len(results)} Q-values from graph")
        except Exception as e:
            logger.error(f"Failed to initialize Q-table from graph: {e}")
    
    async def find_paths(
        self, 
        start_nodes: List[Dict[str, Any]], 
        end_nodes: Optional[List[Dict[str, Any]]] = None,
        max_hops: int = 5
    ) -> List[MemoryPath]:
        """
        Find optimal paths using Q-values for guidance.
        
        Args:
            start_nodes: Starting nodes for traversal
            end_nodes: Target nodes (optional for exploratory search)
            max_hops: Maximum path length
            
        Returns:
            List of MemoryPath objects ranked by Q-values
        """
        paths = []
        
        for start in start_nodes:
            if end_nodes:
                # Directed search to specific targets
                for end in end_nodes:
                    path = await self._q_guided_search(
                        start, end, max_hops
                    )
                    if path:
                        paths.append(path)
            else:
                # Exploratory search in neighborhood
                explored_paths = await self._explore_neighborhood(
                    start, max_hops
                )
                paths.extend(explored_paths)
        
        # Rank paths by Q-values
        return self._rank_paths(paths)
    
    async def _q_guided_search(
        self,
        start: Dict[str, Any],
        end: Dict[str, Any],
        max_hops: int
    ) -> Optional[MemoryPath]:
        """
        Perform Q-value guided search between two nodes.
        
        Uses epsilon-greedy strategy for exploration vs exploitation.
        """
        current_node = start["name"]
        target_node = end["name"]
        path_nodes = [current_node]
        path_relationships = []
        total_score = 0.0
        
        for hop in range(max_hops):
            # Check if we reached the target
            if current_node == target_node:
                return MemoryPath(
                    nodes=path_nodes,
                    relationships=path_relationships,
                    score=total_score,
                    length=len(path_nodes) - 1
                )
            
            # Get available actions (neighbor nodes)
            neighbors = await self._get_neighbors(current_node)
            if not neighbors:
                break
            
            # Select next node using epsilon-greedy
            if random.random() < self.epsilon:
                # Exploration: random choice
                next_action = random.choice(neighbors)
            else:
                # Exploitation: choose best Q-value
                next_action = self._select_best_action(current_node, neighbors)
            
            # Move to next node
            path_nodes.append(next_action["to_node"])
            path_relationships.append({
                "from": current_node,
                "to": next_action["to_node"],
                "type": next_action.get("type", "RELATES_TO")
            })
            
            # Update score based on Q-value
            state = self._get_state_key(current_node)
            action = self._get_action_key(next_action)
            q_value = self.q_table.get_q_value(state, action)
            total_score += q_value
            
            current_node = next_action["to_node"]
        
        # Return partial path if target not reached
        if path_nodes:
            return MemoryPath(
                nodes=path_nodes,
                relationships=path_relationships,
                score=total_score / len(path_nodes),  # Normalize by length
                length=len(path_nodes) - 1
            )
        
        return None
    
    async def _explore_neighborhood(
        self,
        start: Dict[str, Any],
        max_hops: int
    ) -> List[MemoryPath]:
        """
        Explore the neighborhood around a node using Q-values.
        
        Returns multiple paths ranked by their Q-values.
        """
        paths = []
        visited = set()
        
        async def explore_recursive(node, current_path, current_score, depth):
            if depth >= max_hops or node in visited:
                return
            
            visited.add(node)
            
            # Get neighbors
            neighbors = await self._get_neighbors(node)
            
            for neighbor in neighbors[:3]:  # Limit branching factor
                new_path = current_path + [neighbor["to_node"]]
                
                # Calculate Q-value for this transition
                state = self._get_state_key(node)
                action = self._get_action_key(neighbor)
                q_value = self.q_table.get_q_value(state, action)
                new_score = current_score + q_value
                
                # Create path object
                path = MemoryPath(
                    nodes=new_path,
                    relationships=[],  # Simplified for now
                    score=new_score / len(new_path),
                    length=len(new_path) - 1
                )
                paths.append(path)
                
                # Recursive exploration
                await explore_recursive(
                    neighbor["to_node"],
                    new_path,
                    new_score,
                    depth + 1
                )
        
        # Start exploration
        await explore_recursive(
            start["name"],
            [start["name"]],
            0.0,
            0
        )
        
        return paths
    
    async def update_q_values(self, path: List[Any], reward: float):
        """
        Update Q-values based on the success of a path.
        
        Args:
            path: The path taken (list of node IDs or names)
            reward: The reward received (based on user feedback or relevance)
        """
        if len(path) < 2:
            return
        
        # Update Q-values for each state-action pair in the path
        for i in range(len(path) - 1):
            state = self._get_state_key(path[i])
            action = self._get_action_key({"from": path[i], "to": path[i + 1]})
            
            # Get current Q-value
            current_q = self.q_table.get_q_value(state, action)
            
            # Get max Q-value for next state
            next_state = self._get_state_key(path[i + 1])
            max_next_q = self.q_table.get_max_q_value(next_state)
            
            # Q-Learning update rule
            new_q = current_q + self.learning_rate * (
                reward + self.discount_factor * max_next_q - current_q
            )
            
            # Update Q-table
            self.q_table.update(state, action, new_q)
            
            # Update Q-value in Neo4j database
            await self._update_q_value_in_graph(path[i], path[i + 1], new_q)
        
        # Track episode
        self.episode_count += 1
        self.total_rewards.append(reward)
        
        # Periodically save Q-table and sync with Neo4j
        if self.episode_count % 100 == 0:
            await self.q_table.save()
            await self.sync_q_values_to_graph()
            logger.info(f"Q-table saved and synced with Neo4j after {self.episode_count} episodes")
    
    async def _update_q_value_in_graph(self, from_node: str, to_node: str, q_value: float):
        """
        Update Q-value as a property on the relationship in the Neo4j graph.
        
        Args:
            from_node: Name of the starting node
            to_node: Name of the ending node
            q_value: The Q-value to store
        """
        query = """
        MATCH (from {name: $from_node}), (to {name: $to_node})
        MERGE (from)-[r:TRANSITION]-(to)
        SET r.q_value = $q_value
        RETURN r
        """
        
        try:
            await asyncio.to_thread(
                self.graph.execute_query,
                query,
                {
                    "from_node": from_node,
                    "to_node": to_node,
                    "q_value": q_value
                }
            )
        except Exception as e:
            logger.error(f"Failed to update Q-value in graph: {e}")
    
    async def sync_q_values_to_graph(self):
        """
        Synchronize all in-memory Q-values with the Neo4j graph.
        This method should be called periodically to ensure consistency.
        """
        logger.info("Synchronizing Q-values with Neo4j graph...")
        
        # Get all state-action pairs from the Q-table
        for state, actions in self.q_table.q_values.items():
            for action, q_value in actions.items():
                # Parse the action key to get from_node and to_node
                if "→" in action:
                    from_node, to_node = action.split("→")
                    await self._update_q_value_in_graph(from_node, to_node, q_value)
        
        logger.info("Q-value synchronization with Neo4j completed")
    
    async def train(self, training_data: List[Tuple[str, str, float]]):
        """
        Train the Q-Learning agent with historical path data.
        
        Args:
            training_data: List of (start_node, end_node, reward) tuples
        """
        logger.info(f"Starting Q-Learning training with {len(training_data)} examples")
        
        for episode in range(min(self.max_episodes, len(training_data))):
            start, end, reward = training_data[episode]
            
            # Find path between nodes
            path = await self._find_shortest_path(start, end)
            if path:
                await self.update_q_values(path, reward)
            
            # Decay exploration rate
            if episode % 100 == 0:
                self.epsilon = max(0.01, self.epsilon * 0.99)
                logger.debug(f"Episode {episode}: ε={self.epsilon:.3f}")
        
        logger.info(f"Training complete. Total episodes: {self.episode_count}")
    
    async def _get_neighbors(self, node: str) -> List[Dict[str, Any]]:
        """Get neighboring nodes from the graph with Q-values."""
        query = """
        MATCH (n {name: $node})-[r]-(neighbor)
        RETURN neighbor.name as to_node, type(r) as type, 
               r.strength as strength, r.q_value as q_value
        LIMIT 10
        """
        
        results = await asyncio.to_thread(
            self.graph.execute_query,
            query,
            {"node": node}
        )
        
        return results or []
    
    async def _find_shortest_path(self, start: str, end: str) -> Optional[List[str]]:
        """Find shortest path between two nodes using Neo4j."""
        query = """
        MATCH path = shortestPath(
            (start {name: $start})-[*]-(end {name: $end})
        )
        RETURN [n in nodes(path) | n.name] as path
        """
        
        result = await asyncio.to_thread(
            self.graph.execute_query,
            query,
            {"start": start, "end": end}
        )
        
        if result and result[0].get("path"):
            return result[0]["path"]
        return None
    
    def _select_best_action(self, state: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the action with the highest Q-value."""
        state_key = self._get_state_key(state)
        best_action = None
        best_q_value = float('-inf')
        
        for action in actions:
            action_key = self._get_action_key(action)
            # First try to get Q-value from in-memory Q-table
            q_value = self.q_table.get_q_value(state_key, action_key)
            
            # If not found in memory, try to get from action data (from graph)
            if q_value == 0.0 and action.get("q_value") is not None:
                q_value = action["q_value"]
            
            if q_value > best_q_value:
                best_q_value = q_value
                best_action = action
        
        return best_action or actions[0]  # Default to first action if no Q-values
    
    def _rank_paths(self, paths: List[MemoryPath]) -> List[MemoryPath]:
        """Rank paths by their scores (Q-values)."""
        return sorted(paths, key=lambda p: p.score, reverse=True)
    
    def _get_state_key(self, node: Any) -> str:
        """Get a hashable state key for a node."""
        if isinstance(node, dict):
            return str(node.get("name", node.get("id", str(node))))
        return str(node)
    
    def _get_action_key(self, action: Any) -> str:
        """Get a hashable action key."""
        if isinstance(action, dict):
            return f"{action.get('from', '')}→{action.get('to_node', action.get('to', ''))}"
        return str(action)
    
    def get_convergence_metrics(self) -> Dict[str, Any]:
        """Get metrics about Q-Learning convergence."""
        if not self.total_rewards:
            return {"converged": False, "episodes": 0}
        
        recent_rewards = self.total_rewards[-100:]
        avg_recent = sum(recent_rewards) / len(recent_rewards) if recent_rewards else 0
        
        return {
            "converged": len(set(recent_rewards[-10:])) == 1,  # Last 10 rewards are same
            "episodes": self.episode_count,
            "average_reward": avg_recent,
            "epsilon": self.epsilon,
            "q_table_size": len(self.q_table.q_values)
        }


class QTable:
    """
    Q-Table implementation with persistence support.
    
    Uses a sparse representation for memory efficiency.
    """
    
    def __init__(self, persist_path: str = None):
        """
        Initialize Q-Table.
        
        Args:
            persist_path: Path to save/load Q-table
        """
        self.persist_path = persist_path
        self.q_values = defaultdict(lambda: defaultdict(float))
    
    def get_q_value(self, state: str, action: str) -> float:
        """Get Q-value for a state-action pair."""
        return self.q_values[state][action]
    
    def get_max_q_value(self, state: str) -> float:
        """Get maximum Q-value for a state."""
        if state not in self.q_values or not self.q_values[state]:
            return 0.0
        return max(self.q_values[state].values())
    
    def update(self, state: str, action: str, value: float):
        """Update Q-value for a state-action pair."""
        self.q_values[state][action] = value
    
    async def save(self):
        """Save Q-table to disk."""
        if not self.persist_path:
            return
        
        try:
            # Convert to regular dict for serialization
            data = {
                state: dict(actions)
                for state, actions in self.q_values.items()
            }
            
            # Save as numpy file
            np.save(self.persist_path, data)
            logger.debug(f"Q-table saved to {self.persist_path}")
            
        except Exception as e:
            logger.error(f"Error saving Q-table: {e}")
    
    async def load(self):
        """Load Q-table from disk."""
        if not self.persist_path:
            return
        
        try:
            import os
            if os.path.exists(self.persist_path):
                data = np.load(self.persist_path, allow_pickle=True).item()
                self.q_values = defaultdict(
                    lambda: defaultdict(float),
                    {
                        state: defaultdict(float, actions)
                        for state, actions in data.items()
                    }
                )
                logger.info(f"Q-table loaded from {self.persist_path}")
        except Exception as e:
            logger.warning(f"Could not load Q-table: {e}")
