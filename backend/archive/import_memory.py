"""
LEGACY: SQLite importer (archived)

This file is part of legacy tooling that uses SQLite to store memory chunks. It
is retained in the archive as a historical and migration helper. Please prefer
Neo4j importers and tools for production usage.

If you must use this file:
 - Install `aiosqlite` package: `pip install aiosqlite`
 - Run with `ECE_ALLOW_LEGACY_SQLITE=1` to explicitly allow legacy behavior
 - Make backups of your `ece_memory.db` before running migration scripts
"""

"""
Import existing memory file into ECE_Core database.
Designed for ADHD/Autism assistance - optimized for retrieval, not perfection.
"""
import asyncio
import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import tiktoken

class MemoryImporter:
    """Import and structure memories for optimal retrieval."""
    
    def __init__(self, db_path: str = "./ece_memory.db"):
        self.db_path = db_path
        self.db = None
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    async def initialize(self):
        """Set up database with enhanced schema for memory types."""
        self.db = await aiosqlite.connect(self.db_path)
        
        # Core memories table - structured for retrieval
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,           -- code, event, idea, task, person
                timestamp TEXT NOT NULL,           -- When it happened/was created
                content TEXT NOT NULL,             -- The actual memory
                tags TEXT,                         -- JSON array of tags for filtering
                importance INTEGER DEFAULT 5,      -- 1-10 scale
                token_count INTEGER,
                metadata TEXT,                     -- JSON for flexible data
                created_at TEXT NOT NULL,
                last_accessed TEXT
            )
        """)
        
        # Indexes for fast retrieval
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_category ON memories(category)")
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
        
        # Timeline table - for temporal navigation
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,                -- YYYY-MM-DD
                event_type TEXT,                   -- work, personal, learning, etc.
                summary TEXT NOT NULL,
                related_memories TEXT,             -- JSON array of memory IDs
                created_at TEXT NOT NULL
            )
        """)
        
        # Connections table - link related memories
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS memory_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_memory_id INTEGER,
                to_memory_id INTEGER,
                connection_type TEXT,              -- references, builds_on, relates_to
                strength INTEGER DEFAULT 5,        -- 1-10
                created_at TEXT NOT NULL
            )
        """)
        
        await self.db.commit()
        print("✓ Database schema created")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
    
    async def import_from_text_file(self, file_path: str, default_category: str = "general"):
        """
        Import memories from a text file.
        
        Simple format:
        - Lines starting with # are headers/categories
        - Blank lines separate memories
        - Everything else is content
        """
        print(f"\n📖 Reading: {file_path}")
        
        content = Path(file_path).read_text(encoding='utf-8')
        
        # Split into chunks (separated by blank lines or headers)
        chunks = []
        current_chunk = []
        current_category = default_category
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Category marker
            if line.startswith('# '):
                if current_chunk:
                    chunks.append((current_category, '\n'.join(current_chunk)))
                    current_chunk = []
                current_category = line[2:].strip().lower()
            
            # Content
            elif line:
                current_chunk.append(line)
            
            # Blank line - end of chunk
            elif current_chunk:
                chunks.append((current_category, '\n'.join(current_chunk)))
                current_chunk = []
        
        # Don't forget last chunk
        if current_chunk:
            chunks.append((current_category, '\n'.join(current_chunk)))
        
        print(f"Found {len(chunks)} memory chunks")
        
        # Import each chunk
        imported = 0
        for category, chunk_content in chunks:
            await self.add_memory(
                category=category,
                content=chunk_content,
                timestamp=datetime.utcnow().isoformat(),
                tags=[],
                importance=5
            )
            imported += 1
        
        print(f"✅ Imported {imported} memories")
        return imported
    
    async def import_from_json(self, file_path: str):
        """
        Import memories from structured JSON.
        
        Format:
        {
            "memories": [
                {
                    "category": "code",
                    "timestamp": "2025-01-15T10:30:00",
                    "content": "Built auth system...",
                    "tags": ["python", "security"],
                    "importance": 8,
                    "metadata": {"project": "ECE"}
                }
            ]
        }
        """
        print(f"\n📖 Reading JSON: {file_path}")
        
        data = json.loads(Path(file_path).read_text(encoding='utf-8'))
        memories = data.get('memories', [])
        
        print(f"Found {len(memories)} memories")
        
        imported = 0
        for mem in memories:
            await self.add_memory(
                category=mem.get('category', 'general'),
                content=mem['content'],
                timestamp=mem.get('timestamp', datetime.utcnow().isoformat()),
                tags=mem.get('tags', []),
                importance=mem.get('importance', 5),
                metadata=mem.get('metadata', {})
            )
            imported += 1
        
        print(f"✅ Imported {imported} memories")
        return imported
    
    async def add_memory(
        self, 
        category: str, 
        content: str, 
        timestamp: str = None,
        tags: List[str] = None,
        importance: int = 5,
        metadata: Dict = None
    ):
        """Add a single memory."""
        if not timestamp:
            timestamp = datetime.utcnow().isoformat()
        
        token_count = self.count_tokens(content)
        created_at = datetime.utcnow().isoformat()
        
        await self.db.execute("""
            INSERT INTO memories 
            (category, timestamp, content, tags, importance, token_count, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            category,
            timestamp,
            content,
            json.dumps(tags or []),
            importance,
            token_count,
            json.dumps(metadata or {}),
            created_at
        ))
        
        await self.db.commit()
    
    async def get_stats(self):
        """Show database statistics."""
        cursor = await self.db.execute("""
            SELECT 
                category,
                COUNT(*) as count,
                SUM(token_count) as total_tokens,
                AVG(importance) as avg_importance
            FROM memories
            GROUP BY category
            ORDER BY count DESC
        """)
        
        stats = await cursor.fetchall()
        
        print("\n📊 Memory Statistics:")
        print(f"{'Category':<15} {'Count':<10} {'Tokens':<15} {'Avg Importance':<15}")
        print("-" * 60)
        
        total_count = 0
        total_tokens = 0
        
        for cat, count, tokens, avg_imp in stats:
            print(f"{cat:<15} {count:<10} {tokens or 0:<15} {avg_imp or 0:<15.1f}")
            total_count += count
            total_tokens += (tokens or 0)
        
        print("-" * 60)
        print(f"{'TOTAL':<15} {total_count:<10} {total_tokens:<15}")
        print()
        
        return stats
    
    async def close(self):
        """Close database."""
        if self.db:
            await self.db.close()


async def main():
    """Interactive import tool."""
    import sys
    
    print("=" * 60)
    print("  ECE Memory Importer")
    print("  For ADHD/Autism Cognitive Assistance")
    print("=" * 60)
    print()
    
    importer = MemoryImporter()
    await importer.initialize()
    
    if len(sys.argv) > 1:
        # Command line mode
        file_path = sys.argv[1]
        
        if file_path.endswith('.json'):
            await importer.import_from_json(file_path)
        else:
            # Detect category from filename or use default
            category = Path(file_path).stem.lower()
            await importer.import_from_text_file(file_path, category)
        
        await importer.get_stats()
    else:
        # Interactive mode
        print("Import Options:")
        print("  1. Import from text file")
        print("  2. Import from JSON file")
        print("  3. Add single memory")
        print("  4. Show statistics")
        print("  5. Exit")
        print()
        
        choice = input("Choose option (1-5): ").strip()
        
        if choice == '1':
            file_path = input("Text file path: ").strip()
            category = input("Default category (or press Enter for filename): ").strip()
            if not category:
                category = Path(file_path).stem.lower()
            await importer.import_from_text_file(file_path, category)
            await importer.get_stats()
        
        elif choice == '2':
            file_path = input("JSON file path: ").strip()
            await importer.import_from_json(file_path)
            await importer.get_stats()
        
        elif choice == '3':
            print("\nAdd Memory:")
            category = input("Category (code/event/idea/task/person): ").strip()
            content = input("Content: ").strip()
            tags_input = input("Tags (comma-separated): ").strip()
            tags = [t.strip() for t in tags_input.split(',')] if tags_input else []
            importance = int(input("Importance (1-10): ").strip() or "5")
            
            await importer.add_memory(category, content, tags=tags, importance=importance)
            print("✅ Memory added")
        
        elif choice == '4':
            await importer.get_stats()
    
    await importer.close()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
