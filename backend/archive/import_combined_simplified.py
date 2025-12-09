"""
LEGACY: Simplified SQLite importer (archived)

This file contains a simplified legacy importer that writes to SQLite. It's
retained in the archive for historical/migration purposes only and requires
`aiosqlite` to run. For production or current imports, use the Neo4j importers.
"""

"""
Import your 84MB combined context file into ECE_Core.

This intelligently chunks and categorizes your conversations with Sybil/Coda.
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from THE_GREAT_SIMPLIFICATION import UnifiedMemoryManager


class ContextImporter:
    """Import large conversation history into memory system."""
    
    def __init__(self, memory_manager: UnifiedMemoryManager):
        self.memory = memory_manager
        self.chunk_size = 4000  # Tokens per memory chunk
        
    async def import_file(self, filepath: str, session_id: str = "history"):
        """
        Import combined context file.
        
        Strategies:
        1. Split by conversation boundaries
        2. Detect timestamps if present
        3. Categorize by content type (code, discussion, etc.)
        4. Maintain chronological order
        """
        print(f"📚 Importing {filepath}...")
        
        content = Path(filepath).read_text(encoding='utf-8')
        total_size = len(content)
        
        print(f"  File size: {total_size:,} characters")
        print(f"  Estimated tokens: {total_size // 4:,}")
        
        # Strategy 1: Try to detect conversation turns
        chunks = self._smart_split(content)
        
        print(f"  Split into {len(chunks)} chunks")
        print(f"  Starting import...\n")
        
        for i, chunk in enumerate(chunks):
            # Detect category
            category = self._detect_category(chunk)
            
            # Detect importance
            importance = self._assess_importance(chunk)
            
            # Extract timestamp if present
            timestamp = self._extract_timestamp(chunk)
            
            # Store
            memory_id = await self.memory.remember(
                session_id=session_id,
                content=chunk,
                category=category,
                importance=importance,
                metadata={
                    'source': 'combined_context',
                    'chunk_index': i,
                    'original_timestamp': timestamp
                }
            )
            
            if (i + 1) % 100 == 0:
                print(f"  Processed {i+1}/{len(chunks)} chunks...")
        
        print(f"\n✅ Import complete! {len(chunks)} memories stored")
        
        # Print stats
        await self._print_stats(session_id)
    
    def _smart_split(self, content: str) -> list[str]:
        """
        Split content intelligently.
        
        Looks for:
        - Conversation turn markers (User:, Assistant:, etc.)
        - Timestamp patterns
        - Natural breaks (multiple newlines)
        - Code blocks
        """
        chunks = []
        
        # Try to find conversation turns
        # Common patterns: "User:", "Human:", "You:", "Assistant:", etc.
        turn_pattern = r'(?:^|\n)(?:User|Human|You|Assistant|AI|Sybil|Coda):\s*'
        
        turns = re.split(turn_pattern, content, flags=re.MULTILINE)
        
        # If we found turns, use them
        if len(turns) > 10:
            print(f"  Found {len(turns)} conversation turns")
            return [t.strip() for t in turns if t.strip() and len(t.strip()) > 50]
        
        # Otherwise, split by paragraphs
        paragraphs = content.split('\n\n')
        
        # Combine small paragraphs into chunks
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < self.chunk_size * 4:  # ~4 chars per token
                current_chunk += "\n\n" + para
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = para
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _detect_category(self, text: str) -> str:
        """Detect what type of content this is."""
        text_lower = text.lower()
        
        # Code indicators
        code_indicators = ['def ', 'class ', 'import ', 'function', '```', 'async ', 'await ']
        if any(ind in text for ind in code_indicators):
            return "code"
        
        # Project/task indicators
        project_indicators = ['project', 'implement', 'build', 'create', 'todo', 'task']
        if any(ind in text_lower for ind in project_indicators):
            return "project"
        
        # Personal/reflection
        personal_indicators = ['i feel', 'i think', 'my', 'autism', 'adhd', 'struggle']
        if any(ind in text_lower for ind in personal_indicators):
            return "personal"
        
        # Research/learning
        research_indicators = ['paper', 'research', 'study', 'learn', 'understand', 'how does']
        if any(ind in text_lower for ind in research_indicators):
            return "research"
        
        return "conversation"
    
    def _assess_importance(self, text: str) -> float:
        """
        Assess how important this memory is.
        
        Factors:
        - Length (more = more important)
        - Keywords (decisions, insights, realizations)
        - Code blocks
        - Personal reflections
        """
        score = 0.5  # Base
        
        # Length
        if len(text) > 1000:
            score += 0.1
        if len(text) > 2000:
            score += 0.1
        
        # Important keywords
        important_words = [
            'important', 'key', 'critical', 'realize', 'insight', 
            'decision', 'breakthrough', 'understand', 'finally'
        ]
        for word in important_words:
            if word in text.lower():
                score += 0.05
        
        # Code
        if '```' in text or 'def ' in text:
            score += 0.1
        
        # Personal insights
        personal_words = ['i realize', 'i understand', 'i see now', 'this changes']
        for word in personal_words:
            if word in text.lower():
                score += 0.1
        
        return min(score, 1.0)
    
    def _extract_timestamp(self, text: str) -> str:
        """Try to extract timestamp from text."""
        # Common timestamp patterns
        patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2025-01-15
            r'\d{2}/\d{2}/\d{4}',  # 01/15/2025
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}',  # Jan 15, 2025
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return ""
    
    async def _print_stats(self, session_id: str):
        """Print import statistics."""
        cursor = await self.memory.sqlite_db.execute("""
            SELECT category, COUNT(*), SUM(token_count), AVG(importance)
            FROM memories
            WHERE session_id = ?
            GROUP BY category
        """, (session_id,))
        
        print("\n📊 Import Statistics:")
        print("-" * 60)
        
        total_memories = 0
        total_tokens = 0
        
        for row in await cursor.fetchall():
            category, count, tokens, avg_importance = row
            total_memories += count
            total_tokens += tokens or 0
            
            print(f"  {category:15s}: {count:5d} memories, {tokens or 0:8,.0f} tokens, "
                  f"importance: {avg_importance:.2f}")
        
        print("-" * 60)
        print(f"  {'TOTAL':15s}: {total_memories:5d} memories, {total_tokens:8,.0f} tokens")
        print()


async def main():
    """Run the import."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python import_combined_simplified.py <path-to-combined-text.txt>")
        print("\nExample:")
        print("  python import_combined_simplified.py combined_text.txt")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    if not Path(filepath).exists():
        print(f"❌ File not found: {filepath}")
        sys.exit(1)
    
    # Initialize memory system
    memory = UnifiedMemoryManager()
    await memory.initialize()
    
    # Import
    importer = ContextImporter(memory)
    
    try:
        await importer.import_file(filepath)
    finally:
        await memory.close()
    
    print("\n✅ Done! Your memories are now searchable.")
    print("\nTry:")
    print("  - Start ECE_Core: python main.py")
    print("  - Ask about past conversations")
    print("  - System will retrieve relevant context automatically")


if __name__ == "__main__":
    asyncio.run(main())
