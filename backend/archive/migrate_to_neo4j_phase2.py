"""
LEGACY / MIGRATION: Phase 2 migration script - archived. This script references
SQLite-based data and is intended for migration steps to Neo4j. Retained in
archive for reference only. Follow backup and isolation advice before running.
"""

"""
Phase 2: Entity Extraction & Graph Building

Extracts entities from Memory nodes and creates semantic relationships.
Reads: Neo4j Memory nodes (5,401 nodes from Phase 1)
Writes: Entity nodes + MENTIONS relationships + Entity-Entity relationships

Output: ~500-1000 Entity nodes + relationship graph
Time: 5-10 minutes
"""
import re
from collections import Counter
from neo4j import GraphDatabase


class Phase2EntityExtractor:
    """Extract entities from Memory nodes and build knowledge graph."""
    
    def __init__(self, bolt_url="bolt://localhost:7687"):
        self.driver = GraphDatabase.driver(bolt_url, auth=None)
        self.stats = {
            'entities_created': 0,
            'mentions_created': 0,
            'relationships_created': 0,
            'errors': 0
        }
        
        # Entity patterns
        self.patterns = {
            'person': r'\b(Rob|Robert|Coda|Sybil|Dory|Claude|ARK|Gemini|DeepSeek)\b',
            'project': r'\b(ECE_Core|External-Context-Engine|Anchor|Llama|Knowledge-Graph)\b',
            'technology': r'\b(Neo4j|Redis|SQLite|Python|FastAPI|UTCP|GraphRAG|Q-Learning)\b',
            'concept': r'\b(memory|context|graph|reasoning|ADHD|autism|consciousness|symbiotic)\b',
        }
    
    def close(self):
        """Close driver connection."""
        if self.driver:
            self.driver.close()
    
    def test_connection(self) -> bool:
        """Test Neo4j connection."""
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (m:Memory) RETURN count(m) as cnt")
                count = result.single()['cnt']
                print(f"✓ Connected to Neo4j ({count:,} Memory nodes)")
                return True
        except Exception as e:
            print(f"✗ Neo4j connection failed: {e}")
            return False
    
    def extract_all_entities(self):
        """Extract entities from all Memory nodes."""
        print("\n🔍 Extracting entities from Memory nodes...\n")
        
        with self.driver.session() as session:
            # Get all Memory content
            result = session.run("""
                MATCH (m:Memory)
                RETURN m.id as id, m.content as content
                LIMIT 5401
            """)
            
            entities = {}
            
            for record in result:
                memory_id = record['id']
                content = record['content'] or ""
                
                # Extract entities by type
                for entity_type, pattern in self.patterns.items():
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    
                    for match in matches:
                        entity_key = match.lower()
                        
                        if entity_key not in entities:
                            entities[entity_key] = {
                                'type': entity_type,
                                'display_name': match,
                                'mentions': [],
                                'count': 0
                            }
                        
                        entities[entity_key]['mentions'].append(memory_id)
                        entities[entity_key]['count'] += 1
            
            print(f"✓ Found {len(entities):,} unique entities across Memory nodes")
            
            # Create Entity nodes in Neo4j
            self._create_entity_nodes(entities)
            
            return entities
    
    def _create_entity_nodes(self, entities: dict):
        """Create Entity nodes in Neo4j."""
        print("📝 Creating Entity nodes...\n")
        
        with self.driver.session() as session:
            # Create Entity label constraint
            try:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
            except:
                pass
            
            batch_size = 100
            entity_list = list(entities.items())
            total = len(entity_list)
            
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = entity_list[batch_start:batch_end]
                
                for entity_key, data in batch:
                    try:
                        session.run("""
                            CREATE (e:Entity {
                                name: $name,
                                type: $type,
                                display_name: $display_name,
                                mention_count: $count,
                                created_at: datetime()
                            })
                        """, {
                            'name': entity_key,
                            'type': data['type'],
                            'display_name': data['display_name'],
                            'count': data['count']
                        })
                        
                        self.stats['entities_created'] += 1
                    
                    except Exception as e:
                        if "already exists" not in str(e):
                            self.stats['errors'] += 1
                
                percent = (batch_end / total) * 100
                print(f"  Progress: {batch_end:,}/{total:,} ({percent:.1f}%)")
        
        print(f"✓ Created {self.stats['entities_created']:,} Entity nodes")
    
    def create_mentions_relationships(self):
        """Create MENTIONS relationships between Memory nodes and Entities."""
        print("\n🔗 Creating MENTIONS relationships...\n")
        
        with self.driver.session() as session:
            # For each entity, create MENTIONS relationships
            result = session.run("MATCH (e:Entity) RETURN e.name as name, e.type as type")
            
            entities = result.data()
            total = len(entities)
            
            for i, entity_data in enumerate(entities):
                entity_name = entity_data['name']
                entity_type = entity_data['type']
                
                # Find memories that mention this entity
                pattern = self.patterns.get(entity_type, "")
                
                try:
                    # Create relationship for all mentions
                    session.run(f"""
                        MATCH (m:Memory), (e:Entity {{name: $entity_name}})
                        WHERE m.content IS NOT NULL 
                        AND m.content =~ $pattern
                        MERGE (m)-[:MENTIONS]->(e)
                    """, {
                        'entity_name': entity_name,
                        'pattern': f"(?i).*\\b{re.escape(entity_name)}\\b.*"
                    })
                    
                    self.stats['mentions_created'] += 1
                
                except Exception as e:
                    self.stats['errors'] += 1
                
                if (i + 1) % 50 == 0:
                    percent = ((i + 1) / total) * 100
                    print(f"  Progress: {i+1:,}/{total:,} ({percent:.1f}%)")
        
        print(f"✓ Created MENTIONS relationships")
    
    def create_entity_relationships(self):
        """Create relationships between related entities."""
        print("\n🔗 Creating Entity-Entity relationships...\n")
        
        with self.driver.session() as session:
            # Find entities mentioned together in memories
            result = session.run("""
                MATCH (m:Memory)-[:MENTIONS]->(e1:Entity)
                WITH m, e1
                MATCH (m)-[:MENTIONS]->(e2:Entity)
                WHERE e1.name < e2.name
                WITH e1, e2, count(*) as co_mention_count
                WHERE co_mention_count > 1
                CREATE (e1)-[:RELATES_TO {weight: co_mention_count}]->(e2)
                RETURN count(*) as relationships_created
            """)
            
            count = result.single()['relationships_created']
            self.stats['relationships_created'] = count
            
            print(f"✓ Created {count:,} Entity-Entity relationships")
    
    def build_stats(self) -> dict:
        """Get statistics from Neo4j."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)
                RETURN 
                    count(e) as total_entities,
                    count(DISTINCT e.type) as entity_types,
                    COLLECT(DISTINCT e.type) as types,
                    max(e.mention_count) as max_mentions
            """)
            
            row = result.single()
            return {
                'total_entities': row['total_entities'],
                'entity_types': row['entity_types'],
                'type_names': row['types'],
                'max_mentions': row['max_mentions']
            }
    
    def _print_stats(self):
        """Print extraction statistics."""
        stats = self.build_stats()
        
        print("\n" + "=" * 60)
        print("  PHASE 2 ENTITY EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"  Total Entity nodes:        {stats['total_entities']:>10,}")
        print(f"  Entity types:              {stats['entity_types']:>10}")
        if stats['type_names']:
            for etype in stats['type_names']:
                count_result = self.driver.session().run(f"MATCH (e:Entity {{type: $t}}) RETURN count(e) as cnt", t=etype)
                count = count_result.single()['cnt']
                print(f"    - {etype:20s}: {count:>10,}")
        print(f"  Max mentions (entity):     {stats['max_mentions']:>10}")
        print(f"  Relationships created:     {self.stats['relationships_created']:>10}")
        print(f"  Errors encountered:        {self.stats['errors']:>10}")
        print("=" * 60)
        print("\n✓ Phase 2 complete!")
        print("  Next: Run migrate_to_neo4j_phase3.py for Q-Learning setup")


def main():
    print("\n" + "=" * 60)
    print("  ECE_Core Neo4j Migration - Phase 2")
    print("  Entity Extraction & Graph Building")
    print("=" * 60)
    
    extractor = Phase2EntityExtractor()
    
    try:
        if not extractor.test_connection():
            return 1
        
        # Extract entities
        entities = extractor.extract_all_entities()
        
        # Build relationships
        extractor.create_mentions_relationships()
        extractor.create_entity_relationships()
        
        # Print stats
        extractor._print_stats()
        
    except Exception as e:
        print(f"\n✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        extractor.close()
    
    return 0


if __name__ == "__main__":
    exit(main())
