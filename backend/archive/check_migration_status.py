"""
Check data migration status for ECE_Core
"""
import sqlite3
import os
from pathlib import Path

# Check combined_text.txt
combined_file = Path("combined_text.txt")
if combined_file.exists():
    size_mb = combined_file.stat().st_size / (1024 * 1024)
    print(f"✓ combined_text.txt: {size_mb:.2f} MB")
    
    # Count lines
    with open(combined_file, 'r', encoding='utf-8') as f:
        lines = sum(1 for _ in f)
    print(f"  Lines: {lines:,}")
else:
    print("✗ combined_text.txt NOT FOUND")

print()

# Check SQLite database
db_file = Path("ece_memory.db")
if db_file.exists():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"✓ SQLite database: {db_file.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"  Tables: {', '.join(tables)}")
    
    # Count data
    if 'memories' in tables:
        cursor.execute("SELECT COUNT(*) FROM memories")
        mem_count = cursor.fetchone()[0]
        print(f"  Memories: {mem_count:,}")
        
        # Sample a few
        cursor.execute("SELECT tag, LENGTH(content) as size FROM memories LIMIT 5")
        samples = cursor.fetchall()
        print(f"  Sample tags: {', '.join([s[0] for s in samples])}")
    
    if 'summaries' in tables:
        cursor.execute("SELECT COUNT(*) FROM summaries")
        sum_count = cursor.fetchone()[0]
        print(f"  Summaries: {sum_count:,}")
    
    if 'conversation_turns' in tables:
        cursor.execute("SELECT COUNT(*) FROM conversation_turns")
        turn_count = cursor.fetchone()[0]
        print(f"  Conversation turns: {turn_count:,}")
        
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM conversation_turns WHERE timestamp IS NOT NULL")
        date_range = cursor.fetchone()
        if date_range[0]:
            print(f"  Date range: {date_range[0]} to {date_range[1]}")
    
    conn.close()
else:
    print("✗ ece_memory.db NOT FOUND")

print()
print("=" * 60)
print("MIGRATION STATUS:")
print("=" * 60)
print("❌ Data NOT migrated to Neo4j yet")
print("❌ Q-Learning NOT trained")
print()
print("Current state:")
print("  - combined_text.txt = RAW chat history (80.7 MB)")
print("  - SQLite = Structured memories/summaries (if any)")
print("  - Neo4j = EMPTY (not running or no data)")
print()
print("Next steps: See migration plan in specs/NEO4J_INTEGRATION.md")
