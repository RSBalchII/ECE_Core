"""
LEGACY: SQLite importer (archived/fixed)

This fixed/import_combined_text file is part of legacy SQLite importers and is
kept for migration/historical purposes only. Prefer Neo4j importers for current
usage.
"""

"""
Import combined_text.txt into ECE_Core memory database.

Works with the new TieredMemory system (Redis + SQLite).
"""
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path
from memory import TieredMemory


class CombinedTextImporter:
    """Import large conversation history into memory system."""
    
    def __init__(self):
        self.memory = None
        self.chunk_size = 4000  # Characters per chunk (roughly 1000 tokens)
        
    async def initialize(self):
        """Initialize memory system."""
        self.memory = TieredMemory()
        await self.memory.initialize()
        print("* Memory system initialized")
    
    async def import_file(self, filepath: str):
        """
        Import combined_text.txt file.
        
        Splits by conversation boundaries and categorizes content.
        """
        print(f"\n** Importing {filepath}...")
        
        if not Path(filepath).exists():
            print(f"* File not found: {filepath}")
            return
        
        content = Path(filepath).read_text(encoding='utf-8')
        total_size = len(content)
        
        print(f"  File size: {total_size:,} characters")
        print(f"  Estimated tokens: {total_size // 4:,}")
        
        # Split into chunks
        chunks = self._smart_split(content)
        
        print(f"  Split into {len(chunks)} chunks")
        print(f"  Starting import...\n")
        
        imported_count = 0
        
        for i, chunk in enumerate(chunks):
            # Detect category
            category = self._detect_category(chunk)
            
            # Extract tags (keywords)
            tags = self._extract_tags(chunk)
            
            # Assess importance
            importance = self._assess_importance(chunk)
            
            # Extract timestamp if present
            timestamp = self._extract_timestamp(chunk)
            
            # Store in memory
            await self.memory.add_memory(
                category=category,
                content=chunk,
                tags=tags,
                importance=importance,
                metadata={
                    'source': 'combined_text.txt',
                    'chunk_index': i,
                    'original_timestamp': timestamp,
                    'imported_at': datetime.utcnow().isoformat()
                }
            )
            
            imported_count += 1
            
            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(chunks)} chunks...")
        
        print(f"\n* Import complete! {imported_count} memories stored")
        
        # Print summary
        await self._print_stats()
    
    def _smart_split(self, content: str) -> list:
        """Split content into intelligent chunks."""
        chunks = []
        
        # Try to find conversation turns
        # Patterns: "User:", "Human:", "You:", "Assistant:", "AI:", "Sybil:", "Coda:"
        turn_pattern = r'(?:^|\n)(?:User|Human|You|Assistant|AI|Sybil|Coda|Claude):\s*'
        
        turns = re.split(turn_pattern, content, flags=re.MULTILINE)
        
        # If we found clear turns, use them
        if len(turns) > 10:
            print(f"  Found {len(turns)} conversation turns")
            return [t.strip() for t in turns if t.strip() and len(t.strip()) > 100]
        
        # Otherwise, split by paragraphs and combine into chunks
        print("  No clear conversation turns, splitting by paragraphs")
        paragraphs = content.split('\n\n')
        
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < self.chunk_size:
                current_chunk += "\n\n" + para
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = para
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _detect_category(self, text: str) -> str:
        """Detect content category."""
        text_lower = text.lower()
        
        # Code indicators
        code_indicators = ['def ', 'class ', 'import ', 'function', '```', 'async ', 'await ', 'const ', 'let ']
        if any(ind in text for ind in code_indicators):
            return "code"
        
        # Event/milestone indicators
        event_indicators = ['completed', 'finished', 'launched', 'started', 'built', 'deployed']
        if any(ind in text_lower for ind in event_indicators):
            return "event"
        
        # Task indicators
        task_indicators = ['need to', 'should', 'must', 'todo', 'next step', 'plan to']
        if any(ind in text_lower for ind in task_indicators):
            return "task"
        
        # Personal/reflection
        personal_indicators = ['i feel', 'i think', 'my adhd', 'my autism', 'diagnosed', 'struggle']
        if any(ind in text_lower for ind in personal_indicators):
            return "person"
        
        # Idea/insight
        idea_indicators = ['insight', 'realization', 'discovered', 'found that', 'learned that']
        if any(ind in text_lower for ind in idea_indicators):
            return "idea"
        
        return "general"
    
    def _extract_tags(self, text: str) -> list:
        """Extract relevant keywords as tags."""
        text_lower = text.lower()
        tags = []
        
        # Common important keywords
        keywords = [
            'adhd', 'autism', 'memory', 'context', 'ece', 'graph', 'redis', 'sqlite', 'neo4j',
            'llama', 'deepseek', 'markovian', 'reasoning', 'july', 'august', 'september',
            'project', 'code', 'build', 'debug', 'fix', 'implement', 'dory', 'sybil', 'coda',
            'python', 'javascript', 'react', 'fastapi', 'api'
        ]
        
        for keyword in keywords:
            if keyword in text_lower:
                tags.append(keyword)
        
        # Limit to top 5 most relevant
        return tags[:5]
    
    def _assess_importance(self, text: str) -> int:
        """Assess importance (1-10 scale)."""
        score = 5  # Default
        
        text_lower = text.lower()
        
        # High importance indicators
        high_importance = ['breakthrough', 'critical', 'important', 'key insight', 'major']
        if any(ind in text_lower for ind in high_importance):
            score += 2
        
        # Decision/action indicators
        decision = ['decided', 'chose', 'implemented', 'solved']
        if any(ind in text_lower for ind in decision):
            score += 1
        
        # Length bonus (longer = often more important)
        if len(text) > 2000:
            score += 1
        
        return min(10, max(1, score))
    
    def _extract_timestamp(self, text: str) -> str:
        """Extract timestamp if present in text."""
        # Look for common date patterns
        patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2024-07-15
            r'\d{2}/\d{2}/\d{4}',  # 07/15/2024
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    async def _print_stats(self):
        """Print import statistics."""
        print("\n" + "="*50)
        print("IMPORT STATISTICS")
        print("="*50)
        
        # Get counts by category
        for category in ['code', 'event', 'idea', 'task', 'person', 'general']:
            memories = await self.memory.get_recent_by_category(category, limit=1000)
            print(f"  {category:12s}: {len(memories):4d} memories")
        
        print("="*50)
    
    async def close(self):
        """Close memory connections."""
        if self.memory:
            await self.memory.close()


async def main():
    """Run the import."""
    print("\n" + "="*50)
    print("  Combined Text Importer")
    print("  ECE_Core Memory System")
    print("="*50)
    
    importer = CombinedTextImporter()
    
    try:
        await importer.initialize()
        await importer.import_file("combined_text.txt")
    except Exception as e:
        print(f"\n* Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await importer.close()
    
    print("\n* All done!")


if __name__ == "__main__":
    asyncio.run(main())
