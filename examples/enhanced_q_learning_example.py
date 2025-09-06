"""
Example implementation of QLearningGraphAgent enhancements using Neo4j's advanced features
"""
import asyncio
import random
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import numpy as np

# Mock Neo4jManager for demonstration
class MockNeo4jManager:
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Mock method to simulate Neo4j query execution."""
        # This is a simplified mock - in reality, this would execute actual Cypher queries
        if "shortestPath" in query:
            return [{"path": ["NodeA", "NodeB", "NodeC"]}]
        elif "apoc.path.expand" in query:
            return [{"to_node": "NodeB", "type": "TRANSITION", "strength": 0.8}]
        elif "gds.pageRank" in query:
            return [{"nodePropertiesWritten": 100, "ranIterations": 20}]
        elif "vector.similarity" in query:
            return [{"state": "SimilarNode1", "similarity": 0.9}, {"state": "SimilarNode2", "similarity": 0.85}]
        else:
            return []

# Enhanced QLearningGraphAgent with Neo4j features
class EnhancedQLearningGraphAgent:
    """
    Enhanced Q-Learning agent for optimal path finding in the knowledge graph
    using Neo4j's advanced features.
    """
    
    def __init__(self, graph_manager, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Enhanced Q-Learning Graph Agent.
        
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
        self.q_table = defaultdict(lambda: defaultdict(float))
        
        # Episode tracking
        self.episode_count = 0
        self.total_rewards = []
        
        # Path cache for efficiency
        self.path_cache = {}
        
        print(f"Enhanced Q-Learning Agent initialized with α={self.learning_rate}, γ={self.discount_factor}, ε={self.epsilon}")
    
    async def find_paths_enhanced(
        self, 
        start_nodes: List[Dict[str, Any]], 
        end_nodes: Optional[List[Dict[str, Any]]] = None,
        max_hops: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find optimal paths using enhanced Neo4j features.
        
        Args:
            start_nodes: Starting nodes for traversal
            end_nodes: Target nodes (optional for exploratory search)
            max_hops: Maximum path length
            
        Returns:
            List of paths ranked by Q-values
        """
        paths = []
        
        for start in start_nodes:
            if end_nodes:
                # Directed search to specific targets using A* if available
                for end in end_nodes:
                    # Try A* first, fallback to standard shortest path
                    path = await self._astar_search(start, end, max_hops)
                    if not path:
                        path = await self._shortest_path_search(start, end, max_hops)
                    if path:
                        paths.append({
                            "nodes": path,
                            "score": self._calculate_path_score(path),
                            "length": len(path) - 1
                        })
            else:
                # Exploratory search in neighborhood using APOC path expansion
                explored_paths = await self._explore_neighborhood_apoc(start, max_hops)
                paths.extend(explored_paths)
        
        # Rank paths by Q-values
        return self._rank_paths(paths)
    
    async def _astar_search(
        self,
        start: Dict[str, Any],
        end: Dict[str, Any],
        max_hops: int
    ) -> Optional[List[str]]:
        """
        Perform A* search between two nodes using Neo4j's APOC library.
        """
        try:
            query = """
            MATCH (start:State {name: $start}), (end:State {name: $end})
            CALL apoc.algo.aStar(start, end, 'TRANSITION', 'weight') 
            YIELD path, weight
            RETURN [n in nodes(path) | n.name] as path, weight
            """
            
            result = self.graph.execute_query(
                query,
                {"start": start["name"], "end": end["name"]}
            )
            
            if result and result[0].get("path"):
                return result[0]["path"]
        except Exception as e:
            print(f"A* search failed, falling back to standard shortest path: {e}")
        
        return None
    
    async def _shortest_path_search(
        self,
        start: Dict[str, Any],
        end: Dict[str, Any],
        max_hops: int
    ) -> Optional[List[str]]:
        """
        Perform standard shortest path search.
        """
        query = """
        MATCH path = shortestPath(
            (start:State {name: $start})-[*..$max_hops]-(end:State {name: $end})
        )
        RETURN [n in nodes(path) | n.name] as path
        """
        
        result = self.graph.execute_query(
            query,
            {"start": start["name"], "end": end["name"], "max_hops": max_hops}
        )
        
        if result and result[0].get("path"):
            return result[0]["path"]
        return None
    
    async def _explore_neighborhood_apoc(
        self,
        start: Dict[str, Any],
        max_hops: int
    ) -> List[Dict[str, Any]]:
        """
        Explore the neighborhood using APOC path expansion.
        """
        paths = []
        
        # Get neighbors using APOC path expansion
        neighbors = await self._get_neighbors_apoc(start["name"])
        
        for neighbor in neighbors:
            # Create a simple path for demonstration
            path = [start["name"], neighbor["to_node"]]
            paths.append({
                "nodes": path,
                "score": self._calculate_path_score(path),
                "length": len(path) - 1
            })
        
        return paths
    
    async def _get_neighbors_apoc(self, node: str) -> List[Dict[str, Any]]:
        """
        Get neighboring nodes using APOC path expansion.
        """
        query = """
        MATCH (n:State {name: $node})
        CALL apoc.path.expandConfig(n, {
          relationshipFilter: "TRANSITION>",
          minLevel: 1,
          maxLevel: 1,
          uniqueness: "NODE_GLOBAL"
        })
        YIELD path
        WITH nodes(path)[-1] as neighbor
        RETURN neighbor.name as to_node, 'TRANSITION' as type
        LIMIT 10
        """
        
        results = self.graph.execute_query(query, {"node": node})
        return results or []
    
    async def calculate_centrality(self):
        """
        Calculate and store centrality scores for all states.
        """
        try:
            query = """
            CALL gds.pageRank.write({
              nodeProjection: 'State',
              relationshipProjection: 'TRANSITION',
              writeProperty: 'pageRankScore'
            })
            YIELD nodePropertiesWritten, ranIterations
            RETURN nodePropertiesWritten, ranIterations
            """
            
            result = self.graph.execute_query(query)
            print(f"Calculated centrality for {result[0]['nodePropertiesWritten']} nodes in {result[0]['ranIterations']} iterations")
            return result
        except Exception as e:
            print(f"Failed to calculate centrality: {e}")
            return None
    
    def get_state_importance(self, state: str) -> float:
        """
        Get importance score for a state based on centrality measures.
        """
        query = """
        MATCH (n:State {name: $state})
        RETURN n.pageRankScore as importance
        """
        result = self.graph.execute_query(query, {"state": state})
        return result[0].get("importance", 0.0) if result else 0.0
    
    async def find_similar_states(self, state: str, k: int = 5):
        """
        Find k most similar states using vector similarity.
        """
        # In a real implementation, we would first get the state's embedding
        # For this example, we'll just return some mock similar states
        query = """
        MATCH (n:State)
        WHERE exists(n.embedding) AND n.name <> $state
        WITH n, rand() as similarity
        ORDER BY similarity DESC
        LIMIT $k
        RETURN n.name as state, similarity
        """
        
        results = self.graph.execute_query(query, {"state": state, "k": k})
        return results
    
    def _select_action_with_centrality(self, state: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select action based on state centrality for exploration.
        """
        state_importance = self.get_state_importance(state)
        
        # If state is highly central, explore less common actions
        if state_importance > 0.7:
            # Prefer actions with lower Q-values (less explored paths)
            return min(actions, key=lambda a: self.q_table[state][self._get_action_key(a)])
        else:
            # Standard epsilon-greedy for less important states
            if random.random() < self.epsilon:
                return random.choice(actions)
            else:
                return self._select_best_action(state, actions)
    
    def _select_best_action(self, state: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the action with the highest Q-value."""
        best_action = None
        best_q_value = float('-inf')
        
        for action in actions:
            action_key = self._get_action_key(action)
            q_value = self.q_table[state][action_key]
            
            if q_value > best_q_value:
                best_q_value = q_value
                best_action = action
        
        return best_action or actions[0]  # Default to first action if no Q-values
    
    def _get_action_key(self, action: Dict[str, Any]) -> str:
        """Get a hashable action key."""
        return f"{action.get('from', '')}→{action.get('to_node', action.get('to', ''))}"
    
    def _calculate_path_score(self, path: List[str]) -> float:
        """Calculate path score based on Q-values."""
        if len(path) < 2:
            return 0.0
        
        total_score = 0.0
        for i in range(len(path) - 1):
            state = path[i]
            action = f"{path[i]}→{path[i+1]}"
            q_value = self.q_table[state][action]
            total_score += q_value
        
        return total_score / len(path)  # Normalize by path length
    
    def _rank_paths(self, paths: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank paths by their scores (Q-values)."""
        return sorted(paths, key=lambda p: p["score"], reverse=True)
    
    async def update_q_values(self, path: List[str], reward: float):
        """
        Update Q-values based on the success of a path.
        
        Args:
            path: The path taken (list of node names)
            reward: The reward received
        """
        if len(path) < 2:
            return
        
        # Update Q-values for each state-action pair in the path
        for i in range(len(path) - 1):
            state = path[i]
            action = f"{path[i]}→{path[i + 1]}"
            
            # Get current Q-value
            current_q = self.q_table[state][action]
            
            # Get max Q-value for next state
            next_state = path[i + 1]
            max_next_q = max(self.q_table[next_state].values()) if self.q_table[next_state] else 0.0
            
            # Q-Learning update rule
            new_q = current_q + self.learning_rate * (
                reward + self.discount_factor * max_next_q - current_q
            )
            
            # Update Q-table
            self.q_table[state][action] = new_q
        
        # Track episode
        self.episode_count += 1
        self.total_rewards.append(reward)
        
        print(f"Updated Q-values for path with reward {reward}")

# Example usage
async def example_usage():
    """Example of how to use the enhanced QLearningGraphAgent."""
    # Initialize mock Neo4j manager
    neo4j_manager = MockNeo4jManager()
    
    # Initialize enhanced QLearningGraphAgent
    config = {
        "learning_rate": 0.1,
        "discount_factor": 0.9,
        "epsilon": 0.1,
        "max_episodes": 1000
    }
    
    agent = EnhancedQLearningGraphAgent(graph_manager=neo4j_manager, config=config)
    
    # Calculate centrality (would populate pageRankScore properties)
    await agent.calculate_centrality()
    
    # Example: Find paths between nodes using enhanced features
    start_nodes = [{"name": "NodeA"}]
    end_nodes = [{"name": "NodeC"}]
    
    print("Finding paths using enhanced Neo4j features...")
    paths = await agent.find_paths_enhanced(start_nodes, end_nodes, max_hops=5)
    print(f"Found {len(paths)} paths")
    
    # Example: Update Q-values based on a successful path
    path = ["NodeA", "NodeB", "NodeC"]
    reward = 0.8
    print("Updating Q-values...")
    await agent.update_q_values(path, reward)
    print("Q-values updated")
    
    # Example: Find similar states
    print("Finding similar states...")
    similar_states = await agent.find_similar_states("NodeA", k=3)
    print(f"Found {len(similar_states)} similar states")

if __name__ == "__main__":
    asyncio.run(example_usage())