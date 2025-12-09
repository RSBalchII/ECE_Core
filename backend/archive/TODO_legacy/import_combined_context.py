"""
Import combined_text.txt into ECE_Core
Processes your 3-month conversation history with Sybil/Coda

SIMPLIFIED VERSION:
1. Parses conversations from combined_text.txt  
2. Markovian chunking (4k token segments)
3. Stores in SQLite for fast search
4. Builds Neo4j hypergraph for Q-Learning
5. Extracts entities and n-ary relationships

Usage:
    python import_combined_context.py
"""

import asyncio
import aiosqlite
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import tiktoken
import re
from dataclasses import dataclass
import hashlib

# Try to import neo4j, make it optional
try:
    from neo4j import AsyncGraphDatabase
    HAS_NEO4J = True
except ImportError:
    print("⚠️  Neo4j driver not installed. Install with: pip install neo4j")
    HAS_NEO4J = False


@dataclass
class ConversationSegment:
    """A chunk of conversation"""
    timestamp: datetime
    participants: List[str]
    content: str
    category: str
    entities: List[str]
    token_count: int
    metadata: Dict[str, Any]


class ContextImporter:
    def __init__(self, sqlite_path: str = "./ece_memory.db", 
                 neo4j_uri: Optional[str] = None,
                 neo4j_user: Optional[str] = None,
                 neo4j_password: Optional[str] = None):
        self.sqlite_path = sqlite_path
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    """
    LEGACY (ARCHIVED)
    This file was moved to `archive/legacy_sqlite/import_combined_context.py`.
    It is provided for archival reference only.
    """

    print("This file is archived. See archive/legacy_sqlite/import_combined_context.py")
                auth=(neo4j_user, neo4j_password) if neo4j_user else None
            )
        
        self.db = None
        
    async def initialize_db(self):
        """Create database schema"""
        self.db = await aiosqlite.connect(self.sqlite_path)
        
        # Memories table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                category TEXT,
                content TEXT NOT NULL,
                summary TEXT,
                token_count INTEGER,
                metadata TEXT
            )
        """)
        
        # Entities table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT,
                first_seen DATETIME,
                last_seen DATETIME,
                mention_count INTEGER DEFAULT 1
            )
        """)
        
        # Relationships table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER,
                entity_id INTEGER,
                relationship_type TEXT,
                strength REAL DEFAULT 1.0,
                FOREIGN KEY (memory_id) REFERENCES memories(id),
                FOREIGN KEY (entity_id) REFERENCES entities(id)
            )
        """)
        
        # Full-text search index
        await self.db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts 
            USING fts5(content, summary)
        """)
        
        await self.db.commit()
        print("✓ SQLite database initialized")
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))
    
    def parse_conversation(self, text: str) -> List[ConversationSegment]:
        """
        Parse combined_files.txt into conversation segments
        
        Looks for patterns like:
        - Timestamp markers
        - Participant names (You, Sybil, Coda)
        - Topic changes
        """
        segments = []
        current_chunk = []
        current_tokens = 0
        max_chunk_tokens = 4000  # Markovian chunk size
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Count tokens in this line
            line_tokens = self.count_tokens(line)
            
            # Check if we should start a new chunk
            if current_tokens + line_tokens > max_chunk_tokens and current_chunk:
                # Save current chunk
                segment = self._create_segment('\n'.join(current_chunk))
                if segment:
                    segments.append(segment)
                
                current_chunk = []
                current_tokens = 0
            
            current_chunk.append(line)
            current_tokens += line_tokens
        
        # Don't forget the last chunk
        if current_chunk:
            segment = self._create_segment('\n'.join(current_chunk))
            if segment:
                segments.append(segment)
        
        return segments
    
    def _create_segment(self, text: str) -> Optional[ConversationSegment]:
        """Create a conversation segment from text"""
        if not text.strip():
            return None
            
        # Extract participants
        participants = []
        if 'Sybil' in text or 'sybil' in text:
            participants.append('Sybil')
        if 'Coda' in text or 'coda' in text:
            participants.append('Coda')
        participants.append('You')  # You're always there
        
        # Categorize
        category = self._categorize_content(text)
        
        # Extract entities (simple version - can be enhanced)
        entities = self._extract_entities(text)
        
        return ConversationSegment(
            timestamp=datetime.now(),  # Will be improved with actual timestamps
            participants=participants,
            content=text,
            category=category,
            entities=entities,
            token_count=self.count_tokens(text),
            metadata={
                'source': 'combined_files.txt',
                'import_date': datetime.now().isoformat()
            }
        )
    
    def _categorize_content(self, text: str) -> str:
        """Categorize content by topic"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['code', 'function', 'class', 'import', 'def', 'async']):
            return 'code'
        elif any(word in text_lower for word in ['remember', 'recall', 'memory', 'context']):
            return 'memory'
        elif any(word in text_lower for word in ['learn', 'understand', 'explain', 'teach']):
            return 'learning'
        elif any(word in text_lower for word in ['ece', 'project', 'build', 'implement']):
            return 'project'
        else:
            return 'conversation'
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities (simple regex-based)"""
        entities = []
        
        # Common entities to look for
        patterns = {
            'person': r'\b(Sybil|Coda|Alice|Bob)\b',
            'tech': r'\b(Redis|SQLite|Neo4j|FastAPI|Python|ECE|HRM|GraphR1)\b',
            'concept': r'\b(memory|context|reasoning|markovian|hierarchical)\b',
        }
        
        for entity_type, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in set(matches):
                entities.append(match)
        
        return list(set(entities))
    
    async def store_segment(self, segment: ConversationSegment, session_id: str = "import"):
        """Store a conversation segment in SQLite"""
        metadata_json = json.dumps(segment.metadata)
        
        cursor = await self.db.execute("""
            INSERT INTO memories (session_id, timestamp, category, content, token_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            segment.timestamp.isoformat(),
            segment.category,
            segment.content,
            segment.token_count,
            metadata_json
        ))
        
        memory_id = cursor.lastrowid
        
        # Store entities
        for entity_name in segment.entities:
            # Get or create entity
            entity_cursor = await self.db.execute(
                "SELECT id FROM entities WHERE name = ?", (entity_name,)
            )
            entity_row = await entity_cursor.fetchone()
            
            if entity_row:
                entity_id = entity_row[0]
                # Update last_seen and increment count
                await self.db.execute("""
                    UPDATE entities 
                    SET last_seen = ?, mention_count = mention_count + 1
                    WHERE id = ?
                """, (segment.timestamp.isoformat(), entity_id))
            else:
                # Create new entity
                new_entity = await self.db.execute("""
                    INSERT INTO entities (name, type, first_seen, last_seen)
                    VALUES (?, ?, ?, ?)
                """, (entity_name, 'unknown', segment.timestamp.isoformat(), segment.timestamp.isoformat()))
                entity_id = new_entity.lastrowid
            
            # Create relationship
            await self.db.execute("""
                INSERT INTO relationships (memory_id, entity_id, relationship_type, strength)
                VALUES (?, ?, ?, ?)
            """, (memory_id, entity_id, 'mentions', 1.0))
        
        # Add to FTS index
        await self.db.execute("""
            INSERT INTO memories_fts (rowid, content) VALUES (?, ?)
        """, (memory_id, segment.content))
        
        await self.db.commit()
        return memory_id
    
    async def import_file(self, file_path: str):
        """Import combined_files.txt"""
        print(f"\n📁 Reading: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        total_tokens = self.count_tokens(text)
        print(f"📊 Total tokens: {total_tokens:,}")
        
        print("\n🔄 Parsing into conversation segments...")
        segments = self.parse_conversation(text)
        print(f"✓ Created {len(segments)} segments")
        
        print("\n💾 Storing in SQLite...")
        for i, segment in enumerate(segments, 1):
            await self.store_segment(segment)
            if i % 10 == 0:
                print(f"  Processed {i}/{len(segments)} segments...")
        
        print(f"\n✅ Import complete!")
        print(f"  - {len(segments)} conversation segments")
        print(f"  - {total_tokens:,} total tokens")
        
        # Show statistics
        cursor = await self.db.execute("SELECT COUNT(DISTINCT name) FROM entities")
        entity_count = (await cursor.fetchone())[0]
        print(f"  - {entity_count} unique entities extracted")
        
        # Show top entities
        cursor = await self.db.execute("""
            SELECT name, mention_count 
            FROM entities 
            ORDER BY mention_count DESC 
            LIMIT 10
        """)
        print("\n📊 Top entities:")
        for row in await cursor.fetchall():
            print(f"  - {row[0]}: {row[1]} mentions")
    
    async def close(self):
        """Close connections"""
        if self.db:
            await self.db.close()
        if self.neo4j_driver:
            await self.neo4j_driver.close()


async def main():
    parser = argparse.ArgumentParser(description='Import combined context file into ECE_Core')
    parser.add_argument('--file', required=True, help='Path to combined_files.txt')
    parser.add_argument('--sqlite', default='./ece_memory.db', help='SQLite database path')
    parser.add_argument('--neo4j-uri', help='Neo4j URI (optional)')
    parser.add_argument('--neo4j-user', help='Neo4j username')
    parser.add_argument('--neo4j-password', help='Neo4j password')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  ECE_Core Context Importer")
    print("=" * 60)
    
    importer = ContextImporter(
        sqlite_path=args.sqlite,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password
    )
    
    try:
        await importer.initialize_db()
        await importer.import_file(args.file)
    finally:
        await importer.close()
    
    print("\n✨ Done! Your context history is now in ECE_Core.")
    print("\nNext steps:")
    print("  1. Start ECE_Core: python main.py")
    print("  2. Query your memories via API")
    print("  3. Build Neo4j graph (coming next)")


if __name__ == "__main__":
    asyncio.run(main())
