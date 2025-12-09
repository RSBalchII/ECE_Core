"""
LEGACY - SQLite Turn Importer

This module provided an importer for conversation turns into a local
SQLite database. The project has since migrated to Neo4j for memory
storage; this module is retained for archival/legacy workflows only.

To enable the legacy SQLite behavior, set environment variable:
`ECE_ALLOW_LEGACY_SQLITE=1` before running.

NOTE: The code is import-safe; if the env var isn't set, the class
will raise a RuntimeError if executed.
"""

import asyncio
import os
if os.getenv("ECE_ALLOW_LEGACY_SQLITE", "0") == "1":
    try:
        import aiosqlite
    except Exception as _e:
        aiosqlite = None
else:
    aiosqlite = None
import json
from datetime import datetime
from typing import List, Optional
from pathlib import Path

# Import our turn extractor
from extract_turns import TurnExtractor, Turn


class TurnImporter:
    def __init__(self, db_path: str = "ece_memory.db"):
        self.db_path = db_path
        if aiosqlite is None:
            raise RuntimeError(
                "Legacy SQLite TurnImporter is disabled. Set ECE_ALLOW_LEGACY_SQLITE=1 and install 'aiosqlite' to enable."
            )
        
    async def init_db(self):
        """Create SQLite tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Conversation turns table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_num INTEGER NOT NULL,
                    timestamp DATETIME,
                    speaker TEXT NOT NULL,
                    content TEXT NOT NULL,
                    thinking TEXT,
                    source_file TEXT,
                    token_count INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index for fast lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_turn 
                ON conversation_turns(session_id, turn_num)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_speaker 
                ON conversation_turns(speaker)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON conversation_turns(timestamp)
            """)
            
            await db.commit()
            print("✓ Database initialized")
    
    async def import_turns(self, turns: List[Turn]):
        """Import turns to SQLite"""
        async with aiosqlite.connect(self.db_path) as db:
            imported = 0
            
            for turn in turns:
                # Estimate token count (rough: 4 chars per token)
                token_count = len(turn.content) // 4
                
                await db.execute("""
                    INSERT INTO conversation_turns 
                    (session_id, turn_num, timestamp, speaker, content, thinking, source_file, token_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    turn.session_id,
                    turn.turn_num,
                    turn.timestamp.isoformat() if turn.timestamp else None,
                    turn.speaker,
                    turn.content,
                    turn.thinking,
                    turn.source_file,
                    token_count
                ))
                imported += 1
                
                if imported % 50 == 0:
                    print(f"  Imported {imported}/{len(turns)} turns...")
            
            await db.commit()
            print(f"✓ Imported {imported} turns to SQLite")
    
    async def get_stats(self):
        """Print database statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total turns
            cursor = await db.execute("SELECT COUNT(*) FROM conversation_turns")
            total = (await cursor.fetchone())[0]
            
            # By speaker
            cursor = await db.execute("""
                SELECT speaker, COUNT(*) 
                FROM conversation_turns 
                GROUP BY speaker
            """)
            by_speaker = await cursor.fetchall()
            
            # By session
            cursor = await db.execute("""
                SELECT session_id, COUNT(*) 
                FROM conversation_turns 
                GROUP BY session_id
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """)
            by_session = await cursor.fetchall()
            
            # Total content size
            cursor = await db.execute("""
                SELECT SUM(LENGTH(content)), SUM(token_count) 
                FROM conversation_turns
            """)
            total_chars, total_tokens = await cursor.fetchone()
            
            print("\n" + "="*60)
            print("DATABASE STATISTICS")
            print("="*60)
            print(f"\nTotal turns: {total:,}")
            print(f"Total characters: {total_chars:,}")
            print(f"Total tokens (est): {total_tokens:,}")
            
            print(f"\nTurns by speaker:")
            for speaker, count in by_speaker:
                print(f"  {speaker}: {count:,}")
            
            print(f"\nTop 10 sessions:")
            for session, count in by_session:
                print(f"  {session:40} {count:4} turns")
            
            print("\n" + "="*60)


async def main():
    print("="*60)
    print("ECE_CORE TURN IMPORTER")
    print("="*60)
    
    # Step 1: Extract turns
    print("\n[Step 1/3] Extracting turns from combined_text.txt...")
    extractor = TurnExtractor()
    turns = extractor.extract_all()
    
    if not turns:
        print("❌ No turns extracted. Check combined_text.txt")
        return
    
    # Step 2: Initialize database
    print("\n[Step 2/3] Initializing SQLite database...")
    importer = TurnImporter()
    await importer.init_db()
    
    # Step 3: Import turns
    print("\n[Step 3/3] Importing turns to database...")
    await importer.import_turns(turns)
    
    # Show stats
    await importer.get_stats()
    
    print("\n✅ Import complete!")
    print("\nNext steps:")
    print("1. Add embeddings: python add_embeddings.py")
    print("2. Build Neo4j graph: python build_graph.py")
    print("3. Test retrieval: python test_retrieval.py")


if __name__ == "__main__":
    asyncio.run(main())
