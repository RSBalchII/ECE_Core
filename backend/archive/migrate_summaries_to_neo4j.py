"""
LEGACY / MIGRATION: This script reads from the legacy `ece_memory.db` SQLite
database and migrates summaries into Neo4j. It is retained for historical
and migration use only. SQLite is deprecated for active ECE_Core usage — Neo4j
is the primary graph storage.

To run (for migration only):
 - Ensure a backup exists of your `ece_memory.db` file
 - Install `aiosqlite` (if missing): `pip install aiosqlite`
 - Run this script in an isolated environment

See `ece-core/archive/legacy_sqlite/README.md` for more details.
"""

"""
Migrate summaries from SQLite to Neo4j and verify.
"""
import asyncio
import aiosqlite
from neo4j import AsyncGraphDatabase


async def migrate_summaries():
    """Migrate all summaries from SQLite to Neo4j."""
    print("\n" + "="*60)
    print("Migrating Summaries: SQLite → Neo4j")
    print("="*60 + "\n")
    
    # Connect to SQLite
    db = await aiosqlite.connect("./ece_memory.db")
    
    # Connect to Neo4j
    neo4j_driver = AsyncGraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )
    
    try:
        # Get all summaries from SQLite
        cursor = await db.execute("""
            SELECT session_id, summary, original_tokens, compressed_tokens, created_at
            FROM summaries
            ORDER BY created_at
        """)
        summaries = await cursor.fetchall()
        
        print(f"Found {len(summaries)} summaries in SQLite")
        
        if len(summaries) == 0:
            print("  No summaries to migrate!")
            return
        
        # Migrate to Neo4j
        async with neo4j_driver.session() as session:
            migrated = 0
            for row in summaries:
                session_id, summary, orig_tokens, comp_tokens, created_at = row
                
                # Create Summary node in Neo4j
                await session.run("""
                    CREATE (s:Summary {
                        session_id: $session_id,
                        summary: $summary,
                        original_tokens: $original_tokens,
                        compressed_tokens: $compressed_tokens,
                        created_at: $created_at
                    })
                """, {
                    "session_id": session_id,
                    "summary": summary,
                    "original_tokens": orig_tokens,
                    "compressed_tokens": comp_tokens,
                    "created_at": created_at
                })
                
                migrated += 1
                if migrated % 10 == 0:
                    print(f"  Migrated {migrated}/{len(summaries)}...")
            
            print(f"\n[OK] Migrated {migrated} summaries to Neo4j")
        
        # Verify migration
        async with neo4j_driver.session() as session:
            result = await session.run("MATCH (s:Summary) RETURN count(s) as count")
            record = await result.single()
            neo4j_count = record["count"]
            
            print(f"[CHECK] Neo4j now has {neo4j_count} Summary nodes")
            
            if neo4j_count == len(summaries):
                print("[OK] Migration verified - counts match!")
            else:
                print(f"[WARN] Count mismatch: SQLite={len(summaries)}, Neo4j={neo4j_count}")
        
    finally:
        await db.close()
        await neo4j_driver.close()
    
    print("\n" + "="*60)
    print("Migration Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(migrate_summaries())
