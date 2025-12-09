"""
Archivist Agent - Intelligent Context Summarization for ECE_Core

Takes large retrieved context and compresses it to fit in context window.
Uses chunked summarization with Markovian state carryover.

Similar to the Archivist from External-Context-Engine but optimized for ECE_Core.
"""
import tiktoken
from typing import List, Dict, Optional
from llm_client import LLMClient
from config import settings


class Archivist:
    """
    Intelligent summarizer that compresses large context.
    
    Strategy:
    1. Break large context into chunks
    2. Summarize each chunk independently
    3. Optionally: meta-summarize chunk summaries if still too large
    4. Return compressed context that fits in window
    """
    
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Config
        self.chunk_size = settings.archivist_chunk_size
        self.overlap = settings.archivist_overlap
        self.compression_ratio = settings.archivist_compression_ratio
        self.max_summary_tokens = settings.archivist_max_summary_tokens
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        Preserves sentence boundaries when possible.
        """
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # Move forward, but overlap
            start += self.chunk_size - self.overlap
        
        return chunks
    
    async def summarize_chunk(self, chunk: str, chunk_index: int, total_chunks: int) -> str:
        """
        Summarize a single chunk of context.
        
        Uses focused prompt to preserve key information.
        """
        system_prompt = """You are an archivist. Your job is to compress information while preserving all key details.

When summarizing:
- Keep names, dates, specific facts
- Preserve technical details and decisions
- Maintain causal relationships
- Use concise but precise language
- No fluff or filler

Output ONLY the compressed summary."""
        
        prompt = f"""Summarize this context (chunk {chunk_index + 1}/{total_chunks}):

{chunk}

Compress to ~{int(self.count_tokens(chunk) * self.compression_ratio)} tokens while keeping all important information:"""
        
        summary = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=self.max_summary_tokens
        )
        
        return summary.strip()
    
    async def meta_summarize(self, summaries: List[str]) -> str:
        """
        Create a meta-summary of chunk summaries.
        Used when chunk summaries are still too large.
        """
        combined = "\n\n---\n\n".join(summaries)
        
        system_prompt = """You are creating a final summary from multiple partial summaries.
Combine them into ONE coherent summary that preserves all critical information."""
        
        prompt = f"""These are summaries of different parts of a conversation.
Create a single unified summary:

{combined}

Target length: ~{self.max_summary_tokens} tokens:"""
        
        meta_summary = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=self.max_summary_tokens
        )
        
        return meta_summary.strip()
    
    async def compress(self, context: str, target_tokens: Optional[int] = None) -> Dict[str, any]:
        """
        Main compression function.
        
        Args:
            context: Large text to compress
            target_tokens: Optional override for max tokens (uses config default otherwise)
        
        Returns:
            {
                "original_text": str,
                "compressed_text": str,
                "original_tokens": int,
                "compressed_tokens": int,
                "compression_ratio": float,
                "chunks_processed": int
            }
        """
        original_tokens = self.count_tokens(context)
        target = target_tokens or self.max_summary_tokens
        
        # If already fits, no compression needed
        if original_tokens <= target:
            return {
                "original_text": context,
                "compressed_text": context,
                "original_tokens": original_tokens,
                "compressed_tokens": original_tokens,
                "compression_ratio": 1.0,
                "chunks_processed": 0
            }
        
        print(f"🗜️  Archivist compressing {original_tokens} tokens → target {target}")
        
        # Step 1: Chunk the context
        chunks = self.chunk_text(context)
        print(f"   Split into {len(chunks)} chunks")
        
        # Step 2: Summarize each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            summary = await self.summarize_chunk(chunk, i, len(chunks))
            chunk_summaries.append(summary)
            print(f"   Chunk {i+1}/{len(chunks)}: {self.count_tokens(chunk)} → {self.count_tokens(summary)} tokens")
        
        # Step 3: Combine summaries
        combined_summary = "\n\n".join(chunk_summaries)
        combined_tokens = self.count_tokens(combined_summary)
        
        # Step 4: Meta-summarize if still too large
        if combined_tokens > target and len(chunk_summaries) > 1:
            print(f"   Meta-summarizing: {combined_tokens} → {target} tokens")
            final_summary = await self.meta_summarize(chunk_summaries)
        else:
            final_summary = combined_summary
        
        final_tokens = self.count_tokens(final_summary)
        
        print(f"✅ Compressed: {original_tokens} → {final_tokens} tokens ({final_tokens/original_tokens:.1%})")
        
        return {
            "original_text": context,
            "compressed_text": final_summary,
            "original_tokens": original_tokens,
            "compressed_tokens": final_tokens,
            "compression_ratio": final_tokens / original_tokens,
            "chunks_processed": len(chunks)
        }
    
    async def compress_retrieved_context(self, sqlite_content: List[Dict]) -> str:
        """
        Compress retrieved SQLite conversation turns.
        
        Args:
            sqlite_content: List of dicts with turn data from qlearning_retriever
                [{"turn_id": 45, "content": "...", "speaker": "...", "timestamp": "..."}]
        
        Returns:
            Compressed context string ready for LLM
        """
        # Format turns into readable context
        formatted_turns = []
        for turn in sqlite_content:
            formatted_turns.append(
                f"[{turn.get('timestamp', 'unknown')}] {turn.get('speaker', 'Unknown')}:\n{turn['content']}"
            )
        
        full_context = "\n\n---\n\n".join(formatted_turns)
        
        # Compress if needed
        result = await self.compress(full_context)
        
        return result["compressed_text"]


async def test_archivist():
    """Test the Archivist agent"""
    print("=" * 60)
    print("  Testing Archivist Agent")
    print("=" * 60)
    
    # Simulate large retrieved context
    test_context = """
[2024-01-15 10:30] Sybil: I've been thinking about how ADHD affects my programming workflow. 
The hyperfocus is great for deep technical problems, but context switching is brutal. 
I lose track of what I was doing if I step away for even 5 minutes.

[2024-01-15 10:32] Coda: That makes sense. Have you tried externalizing your working memory? 
Something like keeping a running notes file of what you're currently thinking about, 
so you can reload that mental state when you return.

[2024-01-15 10:35] Sybil: I've tried various note systems but they all feel like overhead. 
The friction of stopping to write notes breaks my flow. What I really want is something 
that just captures my thought process automatically as I work.

[2024-01-15 10:40] Coda: Interesting. That's essentially what we're building with ECE - 
automated context management. The system should track your conversation history, 
entities you mention, relationships between concepts, without you having to manually maintain it.

[2024-01-15 10:45] Sybil: Exactly! And then when I ask "what was that thing we discussed about 
async patterns last week", it should be able to pull up the relevant context, not just keyword match.
Graph-based retrieval with Q-Learning seems like the right approach.

[2024-01-15 10:50] Coda: Right. The Q-Learning agent learns which graph paths are actually useful 
for different types of queries. Over time it gets better at finding relevant context. 
And the Archivist can compress large contexts to fit in the LLM window.

[2024-01-15 10:55] Sybil: I'm using that Josiefied Qwen3 4B model locally. It's surprisingly good 
for a 4B model - the abliteration helps with creative thinking. With Q6_K quantization it runs 
well on my GPU.
""" * 3  # Triple it to make it large
    
    archivist = Archivist()
    
    print(f"\nOriginal context: {archivist.count_tokens(test_context)} tokens")
    print("\nCompressing...\n")
    
    result = await archivist.compress(test_context, target_tokens=500)
    
    print("\n" + "=" * 60)
    print("  Compression Result")
    print("=" * 60)
    print(f"\nOriginal tokens: {result['original_tokens']}")
    print(f"Compressed tokens: {result['compressed_tokens']}")
    print(f"Compression ratio: {result['compression_ratio']:.1%}")
    print(f"Chunks processed: {result['chunks_processed']}")
    print("\n--- Compressed Text ---")
    print(result['compressed_text'])
    print("\n" + "=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_archivist())
