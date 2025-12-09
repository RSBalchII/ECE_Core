"""
LEGACY / MIGRATION: Phase 3 migration script (archive). This script has been
kept for historical and migration purposes and depends on legacy SQLite data. Use
with caution in staging environments only.
"""

"""
Phase 3: Q-Learning Agent Setup

Prepares Neo4j graph for Q-Learning-based retrieval.
Builds: Path statistics + Q-values on relationships

Output: Relationship traversal statistics ready for learning
Time: 2-5 minutes
"""
from neo4j import GraphDatabase


class Phase3QLearningSetup:
    """Set up Q-Learning infrastructure on Neo4j graph."""
    
    def __init__(self, bolt_url="bolt://localhost:7687"):
        self.driver = GraphDatabase.driver(bolt_url, auth=None)
        self.stats = {
            'paths_analyzed': 0,
            'q_values_initialized': 0,
            'errors': 0
        }
    
    def close(self):
        """Close driver connection."""
        if self.driver:
            self.driver.close()
    
    def test_connection(self) -> bool:
        """Test Neo4j connection."""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (m:Memory)
                    RETURN count(m) as memory_count
                """)
                count = result.single()['memory_count']
                print(f"✓ Connected to Neo4j ({count:,} Memory nodes)")
                return True
        except Exception as e:
            print(f"✗ Neo4j connection failed: {e}")
            return False
    
    def analyze_graph_structure(self):
        """Analyze graph structure for Q-Learning."""
        print("\n📊 Analyzing graph structure...\n")
        
        with self.driver.session() as session:
            # Get relationship statistics
            result = session.run("""
                MATCH (m:Memory)-[r:NEXT]->(m2:Memory)
                RETURN type(r) as rel_type, count(r) as count
                UNION ALL
                MATCH (m:Memory)-[r:MENTIONS]->(e:Entity)
                RETURN type(r) as rel_type, count(r) as count
                UNION ALL
                MATCH (e:Entity)-[r:RELATES_TO]->(e2:Entity)
                RETURN type(r) as rel_type, count(r) as count
            """)
            
            print("Relationship statistics:")
            for record in result:
                rel_type = record['rel_type']
                count = record['count']
                print(f"  {rel_type:15s}: {count:>8,} relationships")
        
        # Analyze paths in new session
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Memory)-[:NEXT]->(m2:Memory)-[:NEXT]->(m3:Memory)
                RETURN count(*) as two_hop_paths
            """)
            
            paths = result.single()['two_hop_paths']
            print(f"\nPath analysis:")
            print(f"  Two-hop NEXT paths: {paths:,}")
            
            self.stats['paths_analyzed'] = paths
    
    def initialize_q_values(self):
        """Initialize Q-values on relationships for learning."""
        print("\n🎯 Initializing Q-values on relationships...\n")
        
        with self.driver.session() as session:
            # Initialize Q-values on NEXT relationships
            result = session.run("""
                MATCH ()-[r:NEXT]->()
                SET r.q_value = 0.0,
                    r.visit_count = 0,
                    r.reward_sum = 0.0
                RETURN count(r) as updated
            """)
            
            next_count = result.single()['updated']
            self.stats['q_values_initialized'] += next_count
            print(f"✓ Initialized Q-values on {next_count:,} NEXT relationships")
        
        with self.driver.session() as session:
            # Initialize weights on RELATES_TO relationships
            result = session.run("""
                MATCH ()-[r:RELATES_TO]->()
                WHERE r.confidence IS NULL
                SET r.confidence = 0.5,
                    r.traversals = 0
                RETURN count(r) as updated
            """)
            
            relates_count = result.single()['updated']
            self.stats['q_values_initialized'] += relates_count
            print(f"✓ Initialized weights on {relates_count:,} RELATES_TO relationships")
    
    def create_query_nodes(self):
        """Create Query nodes for retrieval tracking."""
        print("\n🔎 Creating Query tracking nodes...\n")
        
        with self.driver.session() as session:
            # Create a Query container node
            session.run("""
                MERGE (q:QueryStats {id: "global_stats"})
                SET q.total_queries = 0,
                    q.total_traversals = 0,
                    q.created_at = datetime()
            """)
            
            print("✓ Created Query tracking infrastructure")
    
    def create_learning_metadata(self):
        """Add learning metadata to graph."""
        print("\n📌 Adding learning metadata...\n")
        
        with self.driver.session() as session:
            # Add learning potential scores to entities
            result = session.run("""
                MATCH (e:Entity)
                SET e.learning_potential = toFloat(e.mention_count) / 100.0,
                    e.last_queried = datetime(),
                    e.query_count = 0
                RETURN count(e) as updated
            """)
            
            count = result.single()['updated']
            print(f"✓ Added learning metadata to {count:,} Entity nodes")
            
            # Add traversal metrics to Memory nodes
            result = session.run("""
                MATCH (m:Memory)
                SET m.traversal_count = 0,
                    m.reward = 0.0,
                    m.relevance_score = 0.5
                RETURN count(m) as updated
            """)
            
            mem_count = result.single()['updated']
            print(f"✓ Added traversal metrics to {mem_count:,} Memory nodes")
    
    def create_performance_indexes(self):
        """Create indexes for Q-Learning query performance."""
        print("\n⚡ Creating performance indexes...\n")
        
        with self.driver.session() as session:
            try:
                session.run("CREATE INDEX IF NOT EXISTS FOR ()-[r:NEXT]-() ON (r.q_value)")
                print("✓ Created index on NEXT.q_value")
            except:
                pass
            
            try:
                session.run("CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.learning_potential)")
                print("✓ Created index on Entity.learning_potential")
            except:
                pass
            
            try:
                session.run("CREATE INDEX IF NOT EXISTS FOR (m:Memory) ON (m.traversal_count)")
                print("✓ Created index on Memory.traversal_count")
            except:
                pass
    
    def build_stats(self) -> dict:
        """Get statistics from Neo4j."""
        with self.driver.session() as session:
            # Memory stats
            mem_result = session.run("MATCH (m:Memory) RETURN count(m) as cnt")
            memory_count = mem_result.single()['cnt']
            
            # Entity stats
            entity_result = session.run("MATCH (e:Entity) RETURN count(e) as cnt")
            entity_count = entity_result.single()['cnt']
            
            # Relationship stats
            rel_result = session.run("""
                MATCH ()-[r]->()
                RETURN 
                    count(CASE WHEN type(r) = 'NEXT' THEN 1 END) as next_rels,
                    count(CASE WHEN type(r) = 'MENTIONS' THEN 1 END) as mentions_rels,
                    count(CASE WHEN type(r) = 'RELATES_TO' THEN 1 END) as relates_rels,
                    count(r) as total_rels
            """)
            
            rel_data = rel_result.single()
            
            return {
                'memory_nodes': memory_count,
                'entity_nodes': entity_count,
                'next_relationships': rel_data['next_rels'],
                'mentions_relationships': rel_data['mentions_rels'],
                'relates_relationships': rel_data['relates_rels'],
                'total_relationships': rel_data['total_rels']
            }
    
    def _print_stats(self):
        """Print setup statistics."""
        stats = self.build_stats()
        
        print("\n" + "=" * 60)
        print("  PHASE 3 Q-LEARNING SETUP COMPLETE")
        print("=" * 60)
        print("\nGraph Structure:")
        print(f"  Memory nodes:              {stats['memory_nodes']:>10,}")
        print(f"  Entity nodes:              {stats['entity_nodes']:>10,}")
        print("\nRelationships:")
        print(f"  NEXT (temporal):           {stats['next_relationships']:>10,}")
        print(f"  MENTIONS (semantic):       {stats['mentions_relationships']:>10,}")
        print(f"  RELATES_TO (entity):       {stats['relates_relationships']:>10,}")
        print(f"  Total relationships:       {stats['total_relationships']:>10,}")
        print("\nQ-Learning Infrastructure:")
        print(f"  Q-values initialized on    NEXT relationships")
        print(f"  Traversal tracking         Added to all nodes")
        print(f"  Query statistics           Created")
        print(f"  Performance indexes        Built")
        print("=" * 60)
        print("\n✓ Phase 3 complete!")
        print("\nGraph is ready for Q-Learning-based retrieval!")
        print("Next: Use retrieval/qlearning_retriever.py to query the graph")


def main():
    print("\n" + "=" * 60)
    print("  ECE_Core Neo4j Migration - Phase 3")
    print("  Q-Learning Infrastructure Setup")
    print("=" * 60)
    
    setup = Phase3QLearningSetup()
    
    try:
        if not setup.test_connection():
            return 1
        
        # Analyze structure
        setup.analyze_graph_structure()
        
        # Initialize Q-Learning
        setup.initialize_q_values()
        setup.create_query_nodes()
        setup.create_learning_metadata()
        setup.create_performance_indexes()
        
        # Print stats
        setup._print_stats()
        
    except Exception as e:
        print(f"\n✗ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        setup.close()
    
    return 0


if __name__ == "__main__":
    exit(main())
