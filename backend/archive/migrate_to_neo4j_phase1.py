"""
LEGACY / MIGRATION: This migration script reads SQLite and imports into Neo4j.
It is retained for historic and migration use only. The active ECE_Core uses
Neo4j as the primary memory backend. Use this script only in staging with t he
proper backups and environment settings (install aiosqlite and set
`ECE_ALLOW_LEGACY_SQLITE=1`).
"""

"""
Phase 1: Migrate SQLite conversation data to Neo4j

Reads conversation_turns from ece_memory.db and creates Memory nodes in Neo4j.
Reads: SQLite ece_memory.db (401 conversation turns + 13,445 memories)
Writes: Neo4j Memory nodes + NEXT relationships + Session grouping

Output: ~401 conversation Memory nodes + ~13K memory nodes
Time: 5-10 minutes
"""
import sqlite3
import re
import time
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase


class Phase1Importer:
    """Import SQLite conversation data to Neo4j Memory nodes."""
    
    def __init__(self, bolt_url="bolt://localhost:7687", db_path="ece_memory.db"):
        self.driver = GraphDatabase.driver(bolt_url, auth=None)
        self.db_path = db_path
        self.stats = {
            'conversations_created': 0,
            'memories_created': 0,
            'relationships_created': 0,
            'errors': 0,
        }
    
    def close(self):
        """Close driver connection."""
        if self.driver:
            self.driver.close()
    
    def test_connection(self) -> bool:
        """Test Neo4j connection."""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1")
                print("✓ Connected to Neo4j")
                return True
        except Exception as e:
            print(f"✗ Neo4j connection failed: {e}")
            return False
    
    def test_sqlite_connection(self) -> bool:
        """Test SQLite connection."""
        if not Path(self.db_path).exists():
            print(f"✗ SQLite database not found: {self.db_path}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM conversation_turns")
            count = c.fetchone()[0]
            conn.close()
            print(f"✓ Connected to SQLite ({count:,} conversation turns)")
            return True
        except Exception as e:
            print(f"✗ SQLite connection failed: {e}")
            return False
    
    def clear_existing_data(self):
        """Clear existing Memory nodes and relationships."""
        with self.driver.session() as session:
            result = session.run("MATCH (m:Memory) RETURN count(m) as cnt")
            count = result.single()['cnt']
            
            if count > 0:
                print(f"⚠ Found {count:,} existing Memory nodes")
                response = input("Clear existing data? (y/n): ").strip().lower()
                
                if response == 'y':
                    session.run("MATCH (m:Memory) DETACH DELETE m")
                    print("✓ Cleared existing Memory nodes")
                else:
                    print("! Keeping existing data, will append new memories")
    
    def create_indexes(self):
        """Create Neo4j indexes for performance."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE")
                session.run("CREATE INDEX IF NOT EXISTS FOR (m:Memory) ON (m.timestamp)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (m:Memory) ON (m.speaker)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (m:Memory) ON (m.session_id)")
                print("✓ Indexes created")
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"⚠ Index creation: {e}")
    
    def load_conversation_turns(self) -> list:
        """Load conversation turns from SQLite."""
        print(f"\n📄 Loading from SQLite ({self.db_path})...")
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            SELECT id, session_id, turn_num, timestamp, speaker, content, source_file
            FROM conversation_turns
            ORDER BY session_id, turn_num
        """)
        
        turns = []
        for row in c.fetchall():
            turns.append({
                'id': row[0],
                'session_id': row[1],
                'turn_num': row[2],
                'timestamp': row[3],
                'speaker': row[4],
                'content': row[5],
                'source_file': row[6]
            })
        
        conn.close()
        print(f"  Loaded {len(turns):,} conversation turns from SQLite")
        return turns
    
    def load_memories(self) -> list:
        """Load memories from SQLite."""
        print(f"📄 Loading memories from SQLite...")
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            SELECT id, category, content, tags, importance, metadata
            FROM memories
            LIMIT 5000
        """)
        
        memories = []
        for row in c.fetchall():
            memories.append({
                'id': row[0],
                'category': row[1],
                'content': row[2],
                'tags': row[3],
                'importance': row[4],
                'metadata': row[5]
            })
        
        conn.close()
        print(f"  Loaded {len(memories):,} memories from SQLite (limited to 5000)")
        return memories
    
    def import_conversation_turns(self, turns: list):
        """Import SQLite conversation turns to Neo4j Memory nodes."""
        print(f"\n🔄 Importing {len(turns):,} conversation turns to Neo4j...\n")
        
        with self.driver.session() as session:
            batch_size = 100
            total = len(turns)
            
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = turns[batch_start:batch_end]
                
                for turn in batch:
                    try:
                        memory_id = f"conv_{turn['id']:06d}"
                        
                        session.run("""
                            CREATE (m:Memory {
                                id: $id,
                                source_type: "conversation",
                                speaker: $speaker,
                                content: $content,
                                timestamp: $timestamp,
                                session_id: $session_id,
                                turn_number: $turn_num,
                                source_file: $source_file,
                                created_at: datetime()
                            })
                        """, {
                            'id': memory_id,
                            'speaker': turn['speaker'],
                            'content': turn['content'][:5000],
                            'timestamp': turn['timestamp'],
                            'session_id': turn['session_id'],
                            'turn_num': turn['turn_num'],
                            'source_file': turn['source_file']
                        })
                        
                        self.stats['conversations_created'] += 1
                        
                        # Create NEXT relationship within same session
                        if turn['turn_num'] > 0:
                            prev_id = f"conv_{turn['id'] - 1:06d}"
                            try:
                                session.run("""
                                    MATCH (m1:Memory {id: $prev}), (m2:Memory {id: $curr})
                                    CREATE (m1)-[:NEXT]->(m2)
                                """, {'prev': prev_id, 'curr': memory_id})
                                
                                self.stats['relationships_created'] += 1
                            except:
                                pass  # Relationship may already exist
                    
                    except Exception as e:
                        self.stats['errors'] += 1
                
                percent = (batch_end / total) * 100
                print(f"  Progress: {batch_end:,}/{total:,} ({percent:.1f}%)")
        
        print(f"✓ Imported {self.stats['conversations_created']:,} conversation turns")
    
    def import_memories(self, memories: list):
        """Import SQLite memories to Neo4j Memory nodes."""
        print(f"\n🔄 Importing {len(memories):,} memories to Neo4j...\n")
        
        with self.driver.session() as session:
            batch_size = 100
            total = len(memories)
            
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = memories[batch_start:batch_end]
                
                for mem in batch:
                    try:
                        memory_id = f"mem_{mem['id']:06d}"
                        
                        session.run("""
                            CREATE (m:Memory {
                                id: $id,
                                source_type: "memory",
                                category: $category,
                                content: $content,
                                tags: $tags,
                                importance: $importance,
                                created_at: datetime()
                            })
                        """, {
                            'id': memory_id,
                            'category': mem['category'],
                            'content': mem['content'][:5000],
                            'tags': mem['tags'] or "",
                            'importance': mem['importance'] or 5
                        })
                        
                        self.stats['memories_created'] += 1
                    
                    except Exception as e:
                        self.stats['errors'] += 1
                
                percent = (batch_end / total) * 100
                print(f"  Progress: {batch_end:,}/{total:,} ({percent:.1f}%)")
        
        print(f"✓ Imported {self.stats['memories_created']:,} memories")
    
    def build_stats(self) -> dict:
        """Get statistics from Neo4j."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Memory)
                RETURN 
                    count(m) as total_memories,
                    count(DISTINCT m.speaker) as speakers,
                    count(DISTINCT m.session_id) as sessions,
                    count(CASE WHEN m.source_type = 'conversation' THEN 1 END) as conversations,
                    count(CASE WHEN m.source_type = 'memory' THEN 1 END) as memories
            """)
            
            row = result.single()
            return {
                'total_memories': row['total_memories'],
                'unique_speakers': row['speakers'],
                'sessions': row['sessions'],
                'conversations': row['conversations'],
                'memories': row['memories']
            }
    
    def _print_stats(self):
        """Print import statistics."""
        stats = self.build_stats()
        
        print("\n" + "=" * 60)
        print("  PHASE 1 IMPORT COMPLETE")
        print("=" * 60)
        print(f"  Total Memory nodes:        {stats['total_memories']:>10,}")
        print(f"    - Conversation turns:    {stats['conversations']:>10,}")
        print(f"    - Stored memories:       {stats['memories']:>10,}")
        print(f"  Unique speakers:           {stats['unique_speakers']:>10}")
        print(f"  Session groups:            {stats['sessions']:>10}")
        print(f"  Errors encountered:        {self.stats['errors']:>10}")
        print("=" * 60)
        print("\n✓ Phase 1 complete!")
        print("  Next: Run migrate_to_neo4j_phase2.py for entity extraction")



def main():
    print("\n" + "=" * 60)
    print("  ECE_Core Neo4j Migration - Phase 1")
    print("  SQLite → Memory Nodes")
    print("=" * 60)
    
    importer = Phase1Importer()
    
    try:
        # Test connections
        if not importer.test_connection():
            print("\n✗ Cannot connect to Neo4j. Is launcher running?")
            print("  Run: python launcher.py")
            return 1
        
        if not importer.test_sqlite_connection():
            return 1
        
        # Prepare database
        importer.clear_existing_data()
        importer.create_indexes()
        
        # Load and import data
        start_time = time.time()
        
        print()
        turns = importer.load_conversation_turns()
        importer.import_conversation_turns(turns)
        
        memories = importer.load_memories()
        importer.import_memories(memories)
        
        elapsed = time.time() - start_time
        
        # Print stats
        importer._print_stats()
        print(f"\n⏱ Total time: {elapsed/60:.1f} minutes")
        
    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        importer.close()
    
    return 0


if __name__ == "__main__":
    exit(main())
