"""
LEGACY: SQLite/legacy importer

This script contains logic for importing into a SQLite database and is kept in
the archive for migration/backward compatibility. For current ingestion and
imports, prefer the Neo4j importers available in `ece-core/data_pipeline`.

If you must run legacy importers, install `aiosqlite` and run with
`ECE_ALLOW_LEGACY_SQLITE=1`. Do so only for migration or reproduction.
"""

"""
SIMPLIFIED Context Importer for ECE_Core
Imports combined_text.txt (84MB conversation history) into SQLite + Neo4j

This version:
✅ Markovian chunking (4k tokens per segment)  
✅ SQLite for fast retrieval
✅ Neo4j for GraphR1-style reasoning (optional)
✅ Entity extraction
✅ Progress tracking

Usage:
    python import_combined.py
"""

import asyncio
import aiosqlite
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Optional
import tiktoken
from pathlib import Path

# Optional Neo4j
try:
    from neo4j import AsyncGraphDatabase
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False
    print("ℹ️  Neo4j not installed - skipping graph features")
    

class ContextImporter:
    def __init__(self):
        self.db_path = "ece_memory.db"
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.db = None
        self.neo4j_driver = None
        
        # Stats
        self.total_segments = 0
        self.total_tokens = 0
        
    async def initialize(self):
        """Set up SQLite database"""
        self.db = await aiosqlite.connect(self.db_path)
        
        # Memories table - stores conversation segments
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                speaker TEXT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'conversation',
                token_count INTEGER,
                chunk_index INTEGER,
                metadata TEXT
            )
        """)
        
        # Entities table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT,
                first_mentioned DATETIME,
                mention_count INTEGER DEFAULT 1,
                context TEXT
            )
        """)
        
        # Create indexes for fast search
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_session 
            ON conversation_memories(session_id)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_timestamp 
            ON conversation_memories(timestamp)
        """)
        
        await self.db.commit()
        print("✓ Database initialized")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken"""
        return len(self.tokenizer.encode(text))
    
    def chunk_by_tokens(self, text: str, max_tokens: int = 4000) -> List[str]:
        """
        Markovian chunking: Split text into ~4k token segments
        This mimics HRM's approach of processing fixed-size windows
        """
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        for i in range(0, len(tokens), max_tokens):
            chunk_tokens = tokens[i:i + max_tokens]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
        
        return chunks
    
    def parse_conversation_file(self, filepath: str) -> List[Dict]:
        """
        Parse combined_text.txt into structured conversations
        Handles various formats from your chat history
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to detect conversation boundaries
        # Common patterns: timestamps, speaker labels, etc.
        segments = []
        
        # Split by common separators
        # Adjust these patterns based on your actual file format
        raw_segments = re.split(r'\n(?=\[20\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|User:|Assistant:|Sybil:|Coda:)', content)
        
        for segment in raw_segments:
            if not segment.strip():
                continue
            
            # Extract timestamp if present
            timestamp_match = re.search(r'\[?(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})', segment)
            timestamp = None
            if timestamp_match:
                try:
                    timestamp = datetime.fromisoformat(timestamp_match.group(1))
                except:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()
            
            # Extract speaker
            speaker = "unknown"
            if re.search(r'^(User|Human):', segment, re.MULTILINE):
                speaker = "user"
            elif re.search(r'^(Assistant|Sybil|Coda):', segment, re.MULTILINE):
                speaker = "assistant"
            
            segments.append({
                'timestamp': timestamp,
                'speaker': speaker,
                'content': segment.strip(),
                'tokens': self.count_tokens(segment)
            })
        
        return segments
    
    async def extract_entities(self, text: str) -> List[str]:
        """
        Simple entity extraction
        In a full implementation, you'd use an LLM or NER model
        For now, we'll extract capitalized words as potential entities
        """
        # Basic pattern: capitalized words, exclude common words
        common_words = {'User', 'Assistant', 'The', 'This', 'That', 'These', 'Those', 'I', 'We', 'You', 'They'}
        
        potential_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        entities = [e for e in potential_entities if e not in common_words]
        
        return list(set(entities))  # Unique entities
    
    async def save_to_sqlite(self, segment: Dict, session_id: str, chunk_index: int):
        """Save conversation segment to SQLite"""
        metadata = json.dumps({
            'original_tokens': segment['tokens'],
            'source': 'combined_text.txt'
        })
        
        await self.db.execute("""
            INSERT INTO conversation_memories 
            (session_id, timestamp, speaker, content, token_count, chunk_index, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            segment['timestamp'],
            segment['speaker'],
            segment['content'],
            segment['tokens'],
            chunk_index,
            metadata
        ))
        
        # Extract and store entities
        entities = await self.extract_entities(segment['content'])
        for entity in entities:
            await self.db.execute("""
                INSERT OR IGNORE INTO entities (name, type, first_mentioned)
                VALUES (?, ?, ?)
            """, (entity, 'auto_extracted', segment['timestamp']))
            
            # Increment mention count
            await self.db.execute("""
                UPDATE entities 
                SET mention_count = mention_count + 1
                WHERE name = ?
            """, (entity,))
        
        await self.db.commit()
    
    async def import_file(self, filepath: str, session_id: str = "historical"):
        """Import entire combined_text.txt file"""
        print(f"\n📂 Importing: {filepath}")
        print(f"   Session ID: {session_id}")
        
        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return
        
        # Get file size
        file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
        print(f"   File size: {file_size:.2f} MB")
        
        # Parse file into segments
        print("\n🔍 Parsing conversation segments...")
        segments = self.parse_conversation_file(filepath)
        print(f"   Found {len(segments)} raw segments")
        
        # Process segments with Markovian chunking
        print("\n🧠 Processing with Markovian chunking (4k tokens)...")
        chunk_index = 0
        
        for i, segment in enumerate(segments):
            # If segment is large, chunk it
            if segment['tokens'] > 4000:
                chunks = self.chunk_by_tokens(segment['content'], max_tokens=4000)
                for chunk in chunks:
                    chunk_segment = {
                        'timestamp': segment['timestamp'],
                        'speaker': segment['speaker'],
                        'content': chunk,
                        'tokens': self.count_tokens(chunk)
                    }
                    await self.save_to_sqlite(chunk_segment, session_id, chunk_index)
                    chunk_index += 1
                    self.total_tokens += chunk_segment['tokens']
            else:
                await self.save_to_sqlite(segment, session_id, chunk_index)
                chunk_index += 1
                self.total_tokens += segment['tokens']
            
            self.total_segments = chunk_index
            
            # Progress update every 100 segments
            if i % 100 == 0:
                print(f"   Processed: {i}/{len(segments)} segments ({chunk_index} chunks)")
        
        print(f"\n✅ Import complete!")
        print(f"   Total segments: {self.total_segments}")
        print(f"   Total tokens: {self.total_tokens:,}")
        print(f"   Average tokens/chunk: {self.total_tokens // self.total_segments if self.total_segments else 0}")
    
    async def build_neo4j_graph(self):
        """
        Build Neo4j knowledge hypergraph (GraphR1 style)
        This is where Q-Learning will operate
        """
        if not HAS_NEO4J or not self.neo4j_driver:
            print("\nℹ️  Skipping Neo4j graph building (not configured)")
            return
        
        print("\n🕸️  Building Neo4j knowledge hypergraph...")
        
        # Query all memories
        cursor = await self.db.execute("""
            SELECT id, content, timestamp, speaker
            FROM conversation_memories
            ORDER BY timestamp
        """)
        
        memories = await cursor.fetchall()
        
        async with self.neo4j_driver.session() as session:
            # Create memory nodes
            for memory in memories:
                await session.run("""
                    CREATE (m:Memory {
                        id: $id,
                        content: $content,
                        timestamp: $timestamp,
                        speaker: $speaker
                    })
                """, {
                    'id': memory[0],
                    'content': memory[1][:1000],  # Truncate for Neo4j
                    'timestamp': memory[2],
                    'speaker': memory[3]
                })
            
            print(f"   Created {len(memories)} memory nodes")
            
            # Create entity nodes and relationships
            cursor = await self.db.execute("SELECT name, type, mention_count FROM entities")
            entities = await cursor.fetchall()
            
            for entity in entities:
                await session.run("""
                    CREATE (e:Entity {
                        name: $name,
                        type: $type,
                        mention_count: $mention_count
                    })
                """, {
                    'name': entity[0],
                    'type': entity[1],
                    'mention_count': entity[2]
                })
            
            print(f"   Created {len(entities)} entity nodes")
            
            # TODO: Create relationships based on co-occurrence
            # This is where GraphR1-style hypergraph construction happens
            
        print("   ✓ Neo4j graph built")
    
    async def close(self):
        """Clean up connections"""
        if self.db:
            await self.db.close()
        if self.neo4j_driver:
            await self.neo4j_driver.close()


async def main():
    """Main import process"""
    print("=" * 60)
    print("  ECE_Core Context Importer")
    print("  Converting combined_text.txt → SQLite + Neo4j")
    print("=" * 60)
    
    importer = ContextImporter()
    
    try:
        # Initialize database
        await importer.initialize()
        
        # Import combined_text.txt
        filepath = "combined_text.txt"
        if os.path.exists(filepath):
            await importer.import_file(filepath, session_id="sybil_coda_history")
        else:
            print(f"\n❌ File not found: {filepath}")
            print(f"   Current directory: {os.getcwd()}")
            print(f"   Looking for: {os.path.abspath(filepath)}")
            return
        
        # Optional: Build Neo4j graph
        # await importer.build_neo4j_graph()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await importer.close()
    
    print("\n" + "=" * 60)
    print("  Import Complete! ✨")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Test retrieval: python test_ece.py")
    print("  2. Start ECE_Core: python main.py")
    print("  3. Query your memories via API")


if __name__ == "__main__":
    asyncio.run(main())
