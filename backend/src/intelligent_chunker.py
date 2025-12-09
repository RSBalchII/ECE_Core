"""
Intelligent Chunker: Decides how to process each chunk.

Instead of blindly annotating everything, the Chunker:
1. Analyzes chunk content type (code, prose, logs, etc.)
2. Determines if annotation alone suffices or full detail needed
3. Routes to appropriate processing strategy
"""
from typing import List, Dict, Tuple, Literal
from src.llm import LLMClient
import re


ChunkStrategy = Literal["annotation_only", "distilled", "full_detail"]


class IntelligentChunker:
    """
    Analyzes chunks and routes them to the optimal processing strategy.
    
    This is the "decider" that makes chunking intelligent, not just mechanical.
    """
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.chunk_size = 4000  # chars per chunk
        
    async def process_large_input(
        self, 
        user_input: str,
        query_context: str = ""
    ) -> str:
        """
        Main entry point for processing large user inputs.
        
        Returns a compressed context suitable for the LLM.
        """
        # Detect if input is large enough to warrant chunking
        if len(user_input) < self.chunk_size:
            return user_input  # No chunking needed
        
        # Split into semantic chunks
        chunks = self._split_semantic_chunks(user_input)
        
        # Process each chunk with appropriate strategy
        processed_chunks = []
        for i, chunk in enumerate(chunks):
            strategy = await self._determine_strategy(chunk, query_context)
            processed = await self._process_chunk(chunk, i+1, len(chunks), strategy)
            processed_chunks.append(processed)
        
        # Combine processed chunks
        combined = self._combine_processed_chunks(processed_chunks)
        
        return combined
    
    def _split_semantic_chunks(self, text: str) -> List[str]:
        """
        Split text into chunks at semantic boundaries.
        
        Prefers to split at:
        1. Paragraph breaks (double newline)
        2. Code block boundaries (```)
        3. Section headers (##, ###)
        4. Sentence boundaries (. followed by newline)
        
        Avoids splitting mid-sentence or mid-code-block.
        """
        chunks = []
        current_chunk = ""
        
        # Split on paragraph boundaries first
        paragraphs = text.split('\n\n')
        
        for para in paragraphs:
            # If adding this paragraph exceeds chunk size, save current chunk
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def _determine_strategy(
        self, 
        chunk: str, 
        query_context: str
    ) -> ChunkStrategy:
        """
        Decide processing strategy for this chunk.
        
        Returns:
        - "annotation_only": Just extract meaning, don't send full text
        - "distilled": Compress the chunk, send summary + key details
        - "full_detail": Send entire chunk (code, specs, novel info)
        """
        # Heuristic checks (fast, no LLM needed)
        
        # Code blocks always get full detail
        if "```" in chunk or "def " in chunk or "class " in chunk:
            return "full_detail"

        # If a file path indicating code is present, treat as full detail
        if re.search(r"\b[A-Za-z]:[\\/][\w\-\./\\]+\.py\b", chunk):
            return "full_detail"
        if "Traceback (most recent call last)" in chunk:
            return "distilled"
        
        # Error logs get distilled
        if "ERROR:" in chunk or "Traceback" in chunk or "Exception" in chunk:
            return "distilled"
        
        # Short, simple confirmations get annotation only
        if len(chunk) < 200 and any(word in chunk.lower() for word in 
                                     ["yes", "ok", "agree", "sure", "understood"]):
            return "annotation_only"
        
        # Terminal output (lots of technical info) gets distilled
        if any(marker in chunk for marker in ["INFO:", "WARNING:", "slot ", "srv "]):
            return "distilled"
        
        # For ambiguous cases, ask the LLM (slower but accurate)
        prompt = f"""Analyze this chunk and determine if it needs:
A) annotation_only - Simple, repetitive, or already-known context
B) distilled - Long but compressible (logs, verbose explanations)
C) full_detail - Code, specs, novel information requiring full context

Query context: {query_context[:200]}

Chunk preview:
{chunk[:500]}

Answer with just the letter (A, B, or C):"""
        
        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.1,
            max_tokens=5
        )
        
        # Parse response
        response = response.strip().upper()
        if 'A' in response:
            return "annotation_only"
        elif 'B' in response:
            return "distilled"
        else:
            return "full_detail"
    
    async def _process_chunk(
        self,
        chunk: str,
        chunk_num: int,
        total_chunks: int,
        strategy: ChunkStrategy
    ) -> Dict[str, str]:
        """
        Process chunk according to determined strategy.
        """
        if strategy == "annotation_only":
            annotation = await self._annotate_chunk(chunk, chunk_num, total_chunks)
            return {
                "strategy": "annotation_only",
                "content": annotation,
                "original_length": len(chunk)
            }
        
        elif strategy == "distilled":
            summary = await self._distill_chunk(chunk, chunk_num, total_chunks)
            return {
                "strategy": "distilled",
                "content": summary,
                "original_length": len(chunk)
            }
        
        else:  # full_detail
            annotation = await self._annotate_chunk(chunk, chunk_num, total_chunks)
            return {
                "strategy": "full_detail",
                "content": chunk,
                "annotation": annotation,
                "original_length": len(chunk)
            }
    
    async def _annotate_chunk(self, chunk: str, chunk_num: int, total: int) -> str:
        """
        Extract meaning/themes from chunk without full content.
        """
        prompt = f"""Chunk {chunk_num}/{total} - Extract key meaning:

{chunk[:3000]}

In 2-3 sentences, state:
1. Main theme/topic
2. Key entities mentioned
3. Any decisions/insights

Be concise:"""
        
        annotation = await self.llm.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=150
        )
        
        return annotation.strip()
    
    async def _distill_chunk(self, chunk: str, chunk_num: int, total: int) -> str:
        """
        Compress chunk while preserving important details.
        """
        prompt = f"""Chunk {chunk_num}/{total} - Distill this down:

{chunk[:3000]}

Provide a compressed version that:
- Keeps critical facts, errors, decisions
- Removes verbose/repetitive content
- Stays under 300 words

Also rate the SALIENCE (importance) from 0.0 to 1.0.
- 1.0 = Critical architecture/decision
- 0.5 = Routine info
- 0.1 = Noise/logs

Format: JSON {{ "summary": "...", "score": 0.8 }}
Distilled version:"""
        
        distilled = await self.llm.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=400
        )
        
        return distilled.strip()
    
    def _combine_processed_chunks(self, processed: List[Dict[str, str]]) -> str:
        """
        Combine processed chunks into final context.
        """
        parts = []
        
        for i, chunk_data in enumerate(processed):
            strategy = chunk_data['strategy']
            
            if strategy == "annotation_only":
                parts.append(f"[Chunk {i+1} summary] {chunk_data['content']}")
            
            elif strategy == "distilled":
                parts.append(f"[Chunk {i+1} distilled]\n{chunk_data['content']}")
            
            else:  # full_detail
                parts.append(
                    f"[Chunk {i+1} - FULL DETAIL]\n"
                    f"Note: {chunk_data['annotation']}\n"
                    f"Content:\n{chunk_data['content']}"
                )
        
        combined = "\n\n".join(parts)
        
        # Add metadata summary
        total_original = sum(c['original_length'] for c in processed)
        compression_ratio = len(combined) / total_original if total_original > 0 else 1
        
        header = f"""🧩 Large context processed ({len(processed)} chunks)
Original: {total_original:,} chars → Compressed: {len(combined):,} chars
Compression: {compression_ratio:.1%}

---

"""
        
        return header + combined
