
"""
Q-Learning based Graph Retrieval Agent for ECE_Core.

Inspired by Graph-R1 paper:
- Learn optimal paths through knowledge hypergraph
- Use RL to find most relevant context
- Multi-hop reasoning over graph structure

This is the "intelligence" in your context system.
"""
import random
import json
import numpy as np
from typing import List, Dict, Any, Tuple, Optional, DefaultDict, Set
from neo4j import GraphDatabase
from collections import defaultdict


class QLearningGraphRetriever:
    """
    Q-Learning agent that learns to navigate your knowledge hypergraph.
    
    The agent learns:
    - Which paths through the graph are most useful
    - How to balance exploration vs exploitation
    - Which entities/relations matter for different queries
    
    This is where the "memory" becomes "intelligent".
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # Q-Learning parameters
        # q_table: mapping state -> mapping(action_key -> q_value)
        self.q_table: DefaultDict[str, DefaultDict[str, float]] = defaultdict(lambda: defaultdict(float))  # Q(state, action)
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.epsilon = 0.3  # Exploration rate

        # Graph traversal parameters
        self.max_hops = 3  # Maximum path depth
        self.max_paths = 5  # Max paths to explore
    
    def get_state(self, current_entity: str, query_embedding: List[float], visited: Set[str]) -> str:
        """
        Create state representation for Q-learning.
        State = (current_entity, query_context, visited_count)
        """
        visited_count = len(visited)
        # Simplified state - in production, would include query similarity
        return f"{current_entity}_v{visited_count}"
    
    def get_possible_actions(self, current_entity: str) -> List[Tuple[str, str]]:
        """
        Get possible next nodes from current entity.
        
        Actions are: (relation_type, target_entity)
        """
        with self.driver.session() as session:
            # Prefer display_name for human-readable labels, but keep raw name for matching
            result = session.run(
                """
                MATCH (start:Entity {id: $entity_id})-[:PARTICIPATES_IN]->(h:HyperEdge)
                MATCH (h)<-[:PARTICIPATES_IN]-(target:Entity)
                WHERE target.id <> $entity_id
                RETURN DISTINCT h.relation as relation,
                                target.id as target_id,
                                COALESCE(target.display_name, target.name) as target_label
                LIMIT 20
                """,
                entity_id=current_entity
            )
            
            actions = []
            for record in result:
                # Use the label (display_name if present) for readability in the action key
                label = record.get('target_label')
                actions.append((
                    f"{record['relation']}_{label}",
                    record['target_id']
                ))
            
            return actions
    
    def choose_action(self, state: str, actions: List[Tuple[str, str]]) -> Optional[Tuple[str, str]]:
        """
        Epsilon-greedy action selection.
        
        With probability epsilon: explore (random action)
        With probability 1-epsilon: exploit (best Q-value action)
        """
        if not actions:
            return None
        
        # Exploration
        if random.random() < self.epsilon:
            return random.choice(actions)
        
        # Exploitation
        best_action = None
        best_q = float('-inf')
        
        for action in actions:
            action_key = f"{action[0]}_{action[1]}"  # relation_target
            q_value = self.q_table[state][action_key]
            
            if q_value > best_q:
                best_q = q_value
                best_action = action
        
        return best_action if best_action else random.choice(actions)
    
    def calculate_reward(self, entity_id: str, query_keywords: List[str], 
                        hyperedge_context: str) -> float:
        """
        Calculate reward for reaching this entity.
        
        Reward is higher if:
        - Entity/hyperedge mentions query keywords
        - Entity is connected to many relevant relations
        - Path is novel (not heavily visited)
        
        This is where you'd integrate more sophisticated relevance scoring.
        """
        reward = 0.0
        
        # Get entity info
        with self.driver.session() as session:
            # Return display_name when available for matching/presentation
            result = session.run(
                """
                MATCH (e:Entity {id: $entity_id})
                OPTIONAL MATCH (e)-[:PARTICIPATES_IN]->(h:HyperEdge)
                RETURN e.name as name, COALESCE(e.display_name, e.name) as display_name, e.type as type,
                       collect(h.context) as contexts,
                       count(h) as relation_count
                """,
                entity_id=entity_id
            )
            
            record = result.single()
            if not record:
                return 0.0
            
            # prefer display_name for user-facing matching
            entity_name = (record.get('display_name') or record.get('name') or "").lower()
            contexts = [c.lower() for c in record['contexts'] if c]
            
            # Reward for keyword match
            for keyword in query_keywords:
                keyword = keyword.lower()
                if keyword in entity_name:
                    reward += 1.0
                
                for context in contexts:
                    if keyword in context:
                        reward += 0.5
            
            # Small reward for being well-connected (hub entities)
            relation_count = record['relation_count']
            reward += min(relation_count * 0.1, 1.0)  # Cap at 1.0
        
        return reward
    
    def update_q_value(self, state: str, action: Tuple[str, str], reward: float, next_state: str):
        """
        Q-Learning update rule:
        Q(s, a) = Q(s, a) + α * [R + γ * max_a' Q(s', a') - Q(s, a)]
        """
        action_key = f"{action[0]}_{action[1]}"
        current_q = self.q_table[state][action_key]
        
        # Get max Q-value for next state
        max_next_q = max(self.q_table[next_state].values()) if self.q_table[next_state] else 0.0
        
        # Update
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state][action_key] = new_q
    
    def find_relevant_subgraph(self, query: str, start_entities: List[str]) -> Dict[str, Any]:
        """
        Use Q-Learning to find relevant subgraph for query.
        
        This is the core Graph-R1 approach:
        1. Start from seed entities (found via keyword search)
        2. Use Q-learning to navigate graph
        3. Collect relevant nodes along learned paths
        4. Return subgraph as context
        
        Returns:
            Dict with:
            - entities: List of relevant entity dicts
            - paths: List of traversed paths
            - hyperedges: Relevant n-ary relations
        """
        query_keywords = [w.lower() for w in query.split() if len(w) > 3]
        
        all_entities: Set[str] = set()
        all_hyperedges: Set[str] = set()
        paths: List[List[str]] = []
        
        # For each starting entity, do Q-learning exploration
        for start_entity in start_entities[:3]:  # Limit starting points
            visited: Set[str] = set()
            current_entity = start_entity
            path = [current_entity]
            
            # Multi-hop traversal
            for hop in range(self.max_hops):
                visited.add(current_entity)
                all_entities.add(current_entity)
                
                # Get state
                state = self.get_state(current_entity, [], visited)
                
                # Get possible actions
                actions = self.get_possible_actions(current_entity)
                
                # Filter out already visited
                actions = [(rel, ent) for rel, ent in actions if ent not in visited]
                
                if not actions:
                    break
                
                # Choose action using Q-learning policy
                action = self.choose_action(state, actions)
                if not action:
                    break
                
                relation, next_entity = action
                
                # Get hyperedge connecting them
                hyperedge_id = self._get_hyperedge(current_entity, next_entity)
                if hyperedge_id:
                    all_hyperedges.add(hyperedge_id)
                
                # Calculate reward
                hyperedge_context = self._get_hyperedge_context(hyperedge_id) if hyperedge_id else ""
                reward = self.calculate_reward(next_entity, query_keywords, hyperedge_context)
                
                # Get next state
                next_visited = visited | {next_entity}
                next_state = self.get_state(next_entity, [], next_visited)
                
                # Update Q-values
                self.update_q_value(state, action, reward, next_state)
                
                # Move to next entity
                current_entity = next_entity
                path.append(current_entity)
                
                # Stop if low reward (learned to avoid this path)
                if reward < 0.1:
                    break
            
            paths.append(path)
        
        # Retrieve full entity and hyperedge data
        entities = self._get_entities_data(list(all_entities))
        hyperedges = self._get_hyperedges_data(list(all_hyperedges))
        
        return {
            "entities": entities,
            "hyperedges": hyperedges,
            "paths": paths
        }
    
    def _get_hyperedge(self, entity1: str, entity2: str) -> Optional[str]:
        """Get hyperedge connecting two entities."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e1:Entity {id: $id1})-[:PARTICIPATES_IN]->(h:HyperEdge)
                MATCH (h)<-[:PARTICIPATES_IN]-(e2:Entity {id: $id2})
                RETURN h.id as hedge_id
                LIMIT 1
                """,
                id1=entity1, id2=entity2
            )
            record = result.single()
            return record['hedge_id'] if record else None
    
    def _get_hyperedge_context(self, hyperedge_id: str) -> str:
        """Get context from hyperedge."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (h:HyperEdge {id: $id}) RETURN h.context as context",
                id=hyperedge_id
            )
            record = result.single()
            return record['context'] if record else ""
    
    def _get_entities_data(self, entity_ids: List[str]) -> List[Dict]:
        """Retrieve full data for list of entities."""
        if not entity_ids:
            return []
        
        with self.driver.session() as session:
            # Return display_name where available and expose a preferred label
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.id IN $ids
                RETURN e.id as id,
                       e.name as name,
                       COALESCE(e.display_name, e.name) as display_name,
                       e.type as type
                """,
                ids=entity_ids
            )

            entities: List[Dict[str, Any]] = []
            for record in result:
                display = record.get('display_name') or record.get('name')
                entities.append({
                    "id": record['id'],
                    "name": record['name'],
                    "display_name": display,
                    # preferred_name is provided for callers that want the human label
                    "preferred_name": display,
                    "type": record['type']
                })

            return entities
    
    def _get_hyperedges_data(self, hyperedge_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve full data for list of hyperedges."""
        if not hyperedge_ids:
            return []
        
        with self.driver.session() as session:
            # Return entity labels preferring display_name when available
            result = session.run(
                """
                MATCH (h:HyperEdge)
                WHERE h.id IN $ids
                OPTIONAL MATCH (h)<-[:PARTICIPATES_IN]-(e:Entity)
                RETURN h.id as id,
                       h.relation as relation,
                       h.context as context,
                       collect(COALESCE(e.display_name, e.name)) as entity_names
                """,
                ids=hyperedge_ids
            )
            
            hyperedges = []
            for record in result:
                hyperedges.append({
                    "id": record['id'],
                    "relation": record['relation'],
                    "context": record['context'],
                    "entities": record['entity_names']
                })
            
            return hyperedges
    
    def find_seed_entities(self, query: str) -> List[str]:
        """
        Find starting entities for graph traversal using keyword search.
        """
        # Normalize keywords to lowercase for matching against name or display_name
        keywords = [w.lower() for w in query.split() if len(w) > 3]

        with self.driver.session() as session:
            # Search entities by either stored name or display_name (case-insensitive)
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE any(keyword IN $keywords WHERE
                      toLower(e.name) CONTAINS keyword OR
                      (exists(e.display_name) AND toLower(e.display_name) CONTAINS keyword)
                )
                RETURN e.id as id
                LIMIT 10
                """,
                keywords=keywords
            )

            return [record['id'] for record in result]
    
    def retrieve(self, query: str, fetch_sqlite_content: bool = True) -> Dict[str, Any]:
        """
        Main retrieval function.
        
        1. Find seed entities via keyword search
        2. Use Q-learning to explore relevant subgraph
        3. Fetch actual conversation content from SQLite for found entities
        
        This is what gets called from ECE_Core to fetch relevant memories.
        """
        # Find starting points
        seed_entities = self.find_seed_entities(query)
        
        if not seed_entities:
            return {"entities": [], "hyperedges": [], "paths": [], "sqlite_content": []}
        
        # Use Q-learning to find relevant subgraph
        subgraph = self.find_relevant_subgraph(query, seed_entities)
        
        # Fetch SQLite conversation content for these entities
        if fetch_sqlite_content:
            sqlite_content = self._fetch_sqlite_content_for_entities(subgraph["entities"])
            subgraph["sqlite_content"] = sqlite_content
        
        return subgraph
    
    def save_q_table(self, filepath: str):
        """Save learned Q-values for reuse."""
        # Convert defaultdict to regular dict for JSON serialization
        q_dict: Dict[str, Dict[str, float]] = {
            state: dict(actions)
            for state, actions in self.q_table.items()
        }
        
        with open(filepath, 'w') as f:
            json.dump(q_dict, f, indent=2)
    
    def load_q_table(self, filepath: str):
        """Load previously learned Q-values."""
        try:
            with open(filepath, 'r') as f:
                q_dict = json.load(f)
            
            # Convert back to defaultdict
            self.q_table: DefaultDict[str, DefaultDict[str, float]] = defaultdict(lambda: defaultdict(float))
            for state, actions in q_dict.items():
                self.q_table[state].update(actions)
            
            print(f"✓ Loaded Q-table with {len(self.q_table)} states")
        except FileNotFoundError:
            print(f"⚠ No Q-table found at {filepath}, starting fresh")
    
    def _fetch_sqlite_content_for_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fetch actual conversation content from SQLite for the entities found in Neo4j.
        
        This is the key link: Neo4j finds relevant structure, SQLite provides content.
        Each Neo4j Entity has sqlite_turn_ids property listing which turns mention it.
        """
        import sqlite3
        
        if not entities:
            return []

        # Collect all SQLite turn IDs from Neo4j entities
        all_turn_ids: Set[int] = set()

        with self.driver.session() as session:
            for entity in entities:
                result = session.run(
                    """
                    MATCH (e:Entity {id: $entity_id})
                    RETURN e.sqlite_turn_ids as turn_ids
                    """,
                    entity_id=entity["id"]
                )
                record = result.single()
                if record and record["turn_ids"]:
                    all_turn_ids.update(record["turn_ids"])
        
        if not all_turn_ids:
            return []
        
        # Fetch conversation content from SQLite
        db_path = "./ece_memory.db"  # Could make this configurable
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        placeholders = ",".join("?" * len(all_turn_ids))
        cursor.execute(f"""
            SELECT id, content, speaker, timestamp, token_count
            FROM conversation_turns
            WHERE id IN ({placeholders})
            ORDER BY timestamp
        """, list(all_turn_ids))
        
        sqlite_content = []
        for row in cursor.fetchall():
            sqlite_content.append({
                "turn_id": row[0],
                "content": row[1],
                "speaker": row[2],
                "timestamp": row[3],
                "token_count": row[4]
            })
        
        conn.close()
        
        return sqlite_content
    
    def close(self):
        """Close Neo4j connection."""
        self.driver.close()


# Example usage
if __name__ == "__main__":
    import os
    
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    
    retriever = QLearningGraphRetriever(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # Test query
    query = "How does Sybil think about programming?"
    result = retriever.retrieve(query)
    
    print(f"\n🔍 Query: {query}")
    print(f"📊 Found {len(result['entities'])} entities, {len(result['hyperedges'])} relations")
    print(f"🛤️ Explored {len(result['paths'])} paths")
    
    if result['entities']:
        print("\n💡 Sample entities:")
        for e in result['entities'][:5]:
            print(f"   - {e['name']} ({e['type']})")
    
    # Save learned Q-values
    retriever.save_q_table("q_table.json")
    
    retriever.close()
