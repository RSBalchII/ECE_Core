"""Context Manager: Assembles context and manages overflow."""
import logging
from typing import Optional
from datetime import datetime, timezone
from src.memory import TieredMemory
from src.llm import LLMClient
from src.distiller import Distiller
from src.intelligent_chunker import IntelligentChunker
from src.config import settings

logger = logging.getLogger(__name__)

class ContextManager:
    def __init__(self, memory: TieredMemory, llm: LLMClient):
        self.memory = memory
        self.llm = llm
        self.distiller = Distiller(llm)  # Context quality gate & extractor
        self.chunker = IntelligentChunker(llm)  # Large input processor
    
    async def build_context(self, session_id: str, user_input: str) -> str:
        """
        Build context from memory tiers with Archivist filtering.
        
    Tiers:
    1. Relevant memories (Neo4j) - Long-term memories relevant to the query
    2. Summaries (Neo4j) - Long-term compressed context
        3. Active (Redis) - Short-term recent conversation
        
        The Archivist filters and consolidates retrieved context to prevent bloat.
        If user_input is very large, IntelligentChunker processes it first.
        """
        # DEBUG: Log build_context entry
        logger.debug(f"=== build_context START for session {session_id} ===")
        logger.debug(f"User input length: {len(user_input)} chars")
        # logger.debug(f"User input: {user_input[:200]}...")
        
        # **NEW**: If user input is large, process it intelligently
        if len(user_input) > 4000:
            logger.info(f"Large input detected ({len(user_input):,} chars), processing with IntelligentChunker...")
            user_input_processed = await self.chunker.process_large_input(
                user_input=user_input,
                query_context=""  # First pass, no context yet
            )
            logger.info(f"Input compressed: {len(user_input):,} → {len(user_input_processed):,} chars")
        else:
            user_input_processed = user_input
        
        # 1. Retrieve relevant long-term memories
        logger.debug("Retrieving relevant memories...")
        relevant_memories = await self._retrieve_relevant_memories(user_input_processed, limit=10)
        logger.debug(f"Retrieved {len(relevant_memories)} relevant memories")
        # logger.debug(f"Memories: {relevant_memories}")
        
        # Get summaries from Neo4j
        logger.debug("Retrieving summaries...")
        summaries = await self.memory.get_summaries(session_id, limit=8)
        logger.debug(f"Retrieved {len(summaries)} summaries")
        # logger.debug(f"Summaries: {summaries}")
        
        # 3. Get recent conversation
        logger.debug("Retrieving active context...")
        active_context = await self.memory.get_active_context(session_id)
        logger.debug(f"Active context length: {len(active_context)} chars")
        # logger.debug(f"Active context: {active_context[:200]}...")
        
        # 4. DISTILLER: Filter and format
        logger.debug("Running Distiller filter...")
        filtered = await self.distiller.filter_and_consolidate(
            query=user_input_processed,
            memories=relevant_memories,
            summaries=summaries,
            active_context=active_context
        )
        logger.debug(f"Distiller returned filtered context")
        # logger.debug(f"Filtered: {filtered}")
        
        # 5. Build final context from filtered results
        parts = []

        # A. Current datetime
        current_dt = datetime.now(timezone.utc)
        formatted_dt = current_dt.strftime("%B %d, %Y at %H:%M:%S UTC")
        parts.append(f"**Current Date & Time:** {formatted_dt}\n<current_datetime>{current_dt.isoformat()}</current_datetime>")

        # B. Recent conversation (This Session)
        # Keeping this early provides continuity
        if filtered["active_context"]:
            recent_turns = "\n".join(filtered["active_context"].split("\n")[-100:])  # Preserve more turns (from 40 to 100)
            logger.debug(f"Adding current conversation ({len(recent_turns)} chars)")
            parts.append(f"# Current Conversation (This Session):\n{recent_turns}")

        # C. Historical Summaries (Moved UP)
        if filtered.get("summaries"):
            hist_parts = []
            for s in filtered['summaries']:
                try:
                    import xml.sax.saxutils as saxutils
                    mp = f'<memory id="" source="neo4j" status="verified" date="">{saxutils.escape(str(s))}</memory>'
                    hist_parts.append(mp)
                except Exception:
                    continue
            parts.append('<historical_summaries>\n' + '\n'.join(hist_parts) + '\n</historical_summaries>')

        # D. Relevant Memories / RAG (Moved UP)
        # This acts as the "background knowledge" section
        if filtered.get("relevant_memories"):
            mem_parts = []
            for mem in filtered['relevant_memories']:
                try:
                    mid = mem.get('id') or mem.get('memory_id') or ''
                    meta = mem.get('metadata') or {}
                    if isinstance(meta, str):
                        import json as _json
                        try:
                            meta = _json.loads(meta)
                        except Exception:
                            meta = {}
                    src = meta.get('source') or mem.get('source') or 'neo4j'
                    status = meta.get('status') or 'unverified'
                    date = mem.get('timestamp') or meta.get('created_at') or ''
                    content = mem.get('content') or ''

                    import xml.sax.saxutils as saxutils
                    esc_content = saxutils.escape(str(content))
                    mp = f'<memory id="{mid}" source="{saxutils.escape(str(src))}" status="{saxutils.escape(str(status))}" date="{saxutils.escape(str(date))}">{esc_content}</memory>'
                    mem_parts.append(mp)
                except Exception:
                    continue
            parts.append("<retrieved_memory>\n" + "\n".join(mem_parts) + "\n</retrieved_memory>")

        # NEW: Context Rotation Protocol to maintain optimal window size for 64k limits
        # Check if active context is getting too large for efficient processing within 64k window
        active_context = filtered["active_context"]
        MAX_CONTEXT_BEFORE_ROTATION = 55000  # Leave buffer for new content and system prompt
        CONTEXT_GIST_THRESHOLD = 25000      # Size at which we consider rotating old context

        if len(active_context) > CONTEXT_GIST_THRESHOLD:
            logger.info(f"Active context ({len(active_context)} chars) exceeds threshold ({CONTEXT_GIST_THRESHOLD}), initiating rotation...")

            # Calculate safe rotation point that preserves recent context
            rotation_point = max(len(active_context) // 2, len(active_context) - 20000)  # Don't cut too aggressively
            old_portion = active_context[:rotation_point]
            recent_portion = active_context[rotation_point:]

            # Create a summary of the old portion using distillation
            try:
                # Distill the old conversation into a compact, meaningful summary
                gist_summary = await self.distiller.make_compact_summary(
                    memories=[{"content": old_portion}],
                    summaries=[],
                    active_context="",
                    new_input=""
                )

                if gist_summary and len(gist_summary.strip()) > 0:
                    logger.debug(f"Created gist summary ({len(gist_summary)} chars) from {len(old_portion)} chars of old context")

                    # Create "gist memory" in Neo4j for long-term reference with proper metadata
                    gist_memory_id = await self.memory.add_memory(
                        session_id=session_id,
                        content=gist_summary,
                        category="context_gist",
                        importance=8,  # High importance for context continuity
                        tags=["gist", "summary", "historical", "context_rotation"],
                        metadata={
                            "original_context_length": len(old_portion),
                            "type": "context_rotation_gist",
                            "rotation_point": rotation_point,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    logger.info(f"Stored context gist in memory with ID: {gist_memory_id}")

                    # Reconstruct context with gist + recent context
                    rotated_context = f"## Prior Context Summary:\n{gist_summary}\n\n## Recent Conversation:\n{recent_portion}"

                    # Update the memory with the rotated context
                    await self.memory.save_active_context(session_id, rotated_context)

                    # Update filtered active_context to reflect the rotated version
                    active_context = rotated_context
                    filtered["active_context"] = rotated_context

                    logger.info(f"Context successfully rotated: {len(active_context)} chars total")
                else:
                    logger.debug("Gist summary was empty, skipping context rotation")
            except Exception as e:
                logger.warning(f"Failed to create gist during context rotation: {e}")
                # Fall back to basic trimming if distillation fails
                if len(active_context) > MAX_CONTEXT_BEFORE_ROTATION:
                    # Simply trim to keep only the most recent portion that fits
                    trimmed_portion = active_context[-MAX_CONTEXT_BEFORE_ROTATION:]
                    await self.memory.save_active_context(session_id, trimmed_portion)
                    active_context = trimmed_portion
                    filtered["active_context"] = trimmed_portion
                    logger.info(f"Fallback: Trimmed context to {len(active_context)} chars")

        # Optional: Append a distiller compact summary to the active context for future turns
        try:
            compact_summary = await self.distiller.make_compact_summary(relevant_memories, summaries, active_context, user_input_processed)
            if compact_summary and len(compact_summary.strip()) > 0:
                # Append only if not already present in the active_context
                if compact_summary.strip() not in (active_context or "")[-1200:]:
                    new_active = (active_context or "") + "\n" + compact_summary
                    await self.memory.save_active_context(session_id, new_active)
                    # Update filtered active_context to include compact summary so prompt contains it
                    filtered["active_context"] = (filtered.get("active_context") or "") + "\n" + compact_summary
        except Exception as e:
            logger.debug(f"Failed to append distiller summary to active context: {e}")

        # E. The User Prompt (Moved to LAST)
        # This ensures the model sees your actual command as the immediate task to perform
        parts.append(f"# What the User Just Said:\n{user_input}")

        return "\n\n".join(parts)
    
    async def _retrieve_relevant_memories(self, query: str, limit: int = 15) -> list:
        """
        ENHANCED: Hybrid memory retrieval (Vector + Full-Text).
        
        1. Vector Search (Semantic) - Finds conceptually related memories
        2. Full-text search (Lexical) - Finds exact keyword matches
        3. Fallback to recent - If no matches found
        """
        # DEBUG: Log memory retrieval
        logger.debug(f"=== _retrieve_relevant_memories START ===")
        logger.debug(f"Query: {query[:100]}...")
        
        memories = []
        seen_ids = set()

        # Strategy 1: Vector Search (Semantic)
        if self.memory.vector_adapter and getattr(self.memory, "_vector_enabled", False):
            try:
                logger.debug("Attempting vector search...")
                # Generate embedding
                embeddings = await self.llm.get_embeddings(query)
                if embeddings and len(embeddings) > 0:
                    embedding = embeddings[0] if isinstance(embeddings[0], list) else embeddings
                    vector_results = await self.memory.vector_adapter.query_vector(embedding, top_k=limit)
                    
                    for res in vector_results:
                        # Convert vector result to memory dict format
                        mem = {
                            "id": res.get("node_id"),
                            "memory_id": res.get("node_id"),
                            "content": res.get("metadata", {}).get("content"),
                            "category": res.get("metadata", {}).get("category"),
                            "importance": res.get("metadata", {}).get("importance", 5),
                            "score": res.get("score"),
                            "source": "vector",
                            "metadata": res.get("metadata", {})
                        }
                        # Filter memory items by provenance / origin rules
                        if not self._memory_is_allowed(mem):
                            continue
                        if mem["id"] and mem["id"] not in seen_ids:
                            memories.append(mem)
                            seen_ids.add(mem["id"])
                    logger.debug(f"Vector search returned {len(vector_results)} results")
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # Strategy 2: Full-text search on actual content
        # Extract key terms (words longer than 3 chars)
        words = query.lower().split()
        keywords = [w.strip('.,!?;:()[]{}') for w in words if len(w) > 3]
        
        # Try each significant keyword with full-text search
        lexical_memories = []
        for keyword in keywords[:5]:  # Top 5 keywords
            results = await self.memory.search_memories_neo4j(
                query_text=keyword,
                limit=limit
            )
            lexical_memories.extend(results)
        
            for m in lexical_memories:
                # ensure metadata is loaded as a dict
                if isinstance(m.get('metadata'), str):
                    try:
                        import json as _json
                        m['metadata'] = _json.loads(m['metadata'])
                    except Exception:
                        m['metadata'] = {}
                m["source"] = "lexical"
                if not self._memory_is_allowed(m):
                    continue
                if m['id'] not in seen_ids:
                    seen_ids.add(m['id'])
                    memories.append(m)
        
        # If we found memories, re-rank/sort them
        if memories:
            # Simple scoring: Vector score (if present) vs Lexical score (if present)
            def score_mem(m: dict):
                base_score = float(m.get('score', 0) or 0)
                imp = float(m.get('importance', 5)) / 10.0
                return base_score + imp * 0.2

            scored_sorted = sorted(memories, key=score_mem, reverse=True)
            return scored_sorted[:limit]
        
        # Strategy 3: Retrieve ContextGist memories that may contain historical context
        # These are compressed summaries of old context that was rotated out
        try:
            logger.debug("Checking for relevant ContextGist memories...")
            context_gist_query = f"context gist {query}" if len(query.split()) < 10 else query
            gist_memories = await self.memory.search_memories_neo4j(
                query_text=context_gist_query,
                category="context_gist",
                limit=5
            )

            for gist in gist_memories:
                # ensure metadata is loaded as a dict
                if isinstance(gist.get('metadata'), str):
                    try:
                        import json as _json
                        gist['metadata'] = _json.loads(gist['metadata'])
                    except Exception:
                        gist['metadata'] = {}
                gist["source"] = "context_gist"
                if not self._memory_is_allowed(gist):
                    continue
                if gist['id'] not in seen_ids:
                    seen_ids.add(gist['id'])
                    memories.append(gist)
                    logger.debug(f"Included ContextGist memory: {gist['id']}")
        except Exception as e:
            logger.warning(f"Failed to retrieve ContextGist memories: {e}")

        # Strategy 4: Recent memories (Fallback)
        if not memories:
            logger.debug("No matches found, falling back to recent memories")
            all_recent = []
            for category in ['event', 'idea', 'task', 'person', 'code', 'general', 'genesis', 'context_gist']:
                recent = await self.memory.get_recent_by_category(category, limit=3)
                all_recent.extend(recent)

            # Sort by importance and recency
            memories = sorted(
                all_recent,
                key=lambda x: (x.get('importance', 0), x.get('created_at', '')),
                reverse=True
            )[:limit]

        # Filter items through same provenance filter
        filtered_memories = []
        for m in memories:
            if self._memory_is_allowed(m):
                filtered_memories.append(m)

        return filtered_memories

    def _memory_is_allowed(self, mem: dict) -> bool:
        """Return True if a memory should be used for injection into prompts.

        Rules:
        - Allow if metadata.status == 'committed'
        - Allow if metadata.app_id exists and metadata.source is not a blacklisted file-based generator
        - Block if content or metadata indicate 'thinking_content' or '[PLANNER]' or 'dry-run'
        - Block if metadata.source indicates combined_text/prompt_logs or simple dev file sources
        """
        try:
            # Conservative defaults
            md = mem.get('metadata') or {}
            if isinstance(md, str):
                import json as _json
                try:
                    md = _json.loads(md)
                except Exception:
                    md = {}
            # If explicit status exists and it's committed, allow
            if md.get('status') == 'committed':
                return True
            # If explicit status exists and not committed, block
            if md.get('status') and md.get('status') != 'committed':
                return False
            # Block obvious dev/test file sources
            src = (md.get('source') or md.get('path') or '')
            if isinstance(src, str):
                lc = src.lower()
                blacklisted = ['combined_text', 'combined_text2', 'prompt-logs', 'prompt_logs', 'calibration_run', 'dry-run', 'dry_run', 'tests/', 'weaver']
                for b in blacklisted:
                    if b in lc:
                        return False
            # Block content and metadata containing 'thinking_content' or planner markers
            cont = (mem.get('content') or '')
            if isinstance(cont, str) and ('thinking_content' in cont or '[planner]' in cont.lower()):
                return False
            if 'thinking_content' in str(md).lower():
                return False
            # If we have a valid app_id, we can generally allow it as a verified source
            if md.get('app_id'):
                return True
            # Otherwise conservatively block to avoid file/text provenance contamination
            return False
        except Exception:
            # If anything goes wrong, be conservative and block the memory from retrieval
            return False
    
    async def update_context(self, session_id: str, user_input: str, assistant_response: str):
        current = await self.memory.get_active_context(session_id)
        new_turn = f"User: {user_input}\nAssistant: {assistant_response}\n"
        updated_context = current + "\n" + new_turn

        token_count = self.memory.count_tokens(updated_context)

        if token_count > settings.summarize_threshold:
            summary = await self._summarize_context(updated_context)
            await self.memory.flush_to_neo4j(session_id, summary, original_tokens=token_count)
            recent_turns = "\n".join(updated_context.split("\n")[-25:])  # Keep more recent turns (from 10 to 25)
            await self.memory.save_active_context(session_id, recent_turns)
        else:
            await self.memory.save_active_context(session_id, updated_context)
    
    async def _summarize_context(self, context: str) -> str:
        """
        CHUNKED Markovian summarization with Distiller annotation.
        
        Instead of choking on large context, process in chunks:
        1. Split context into digestible chunks
        2. Distiller annotates meaning for each chunk
        3. Combine annotations into final summary
        """
        # Token budget: For 8K context model
        # System (200) + Output (1000) + Safety (300) = 1500 reserved
        # Available for input: ~6500 tokens
        CHUNK_SIZE = 5000  # tokens (~20,000 chars)
        
        # Rough token estimation: ~4 chars per token
        char_chunk_size = CHUNK_SIZE * 4
        
        # If context fits in one chunk, process directly
        if len(context) <= char_chunk_size:
            return await self._summarize_single_chunk(context)
        
        # Otherwise, chunk and process iteratively
        print(f"🧩 Large context detected ({len(context)} chars) - chunking...")
        
        chunks = []
        start = 0
        while start < len(context):
            end = min(start + char_chunk_size, len(context))
            chunk_text = context[start:end]
            chunks.append(chunk_text)
            start = end
        
        print(f"   Split into {len(chunks)} chunks")
        
        # Process each chunk with Distiller
        annotated_chunks = []
        for i, chunk in enumerate(chunks):
            print(f"   Processing chunk {i+1}/{len(chunks)}...")
            
            # Distiller annotates the chunk's meaning
            annotation = await self.distiller.annotate_chunk(chunk, chunk_number=i+1, total_chunks=len(chunks))
            annotated_chunks.append(f"[Chunk {i+1}] {annotation}")
        
        # Combine all annotations into a coherent summary
        combined = "\n\n".join(annotated_chunks)
        
        # Final compression pass
        final_summary = await self._compress_annotations(combined)
        
        print(f"✅ Chunked summary complete")
        return final_summary
    
    async def _summarize_single_chunk(self, context: str) -> str:
        """Summarize a single chunk of context - preserve granular details."""
        system_prompt = """You are a memory summarizer. Create a comprehensive summary that preserves granular details.

Focus on:
- EXACT facts, numbers, and entity names (never generalize)
- All decisions and conclusions reached
- Different perspectives or options discussed
- Open questions and follow-ups
- Technical details, configurations, or specifications
- Specific code snippets or examples

Preserve specificity. This summary will be the ONLY memory of this conversation."""

        summary = await self.llm.generate(
            prompt=f"Summarize this conversation:\n\n{context}",
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1200  # Increased from 1000 to allow more detail
        )
        return summary
    
    async def _compress_annotations(self, combined_annotations: str) -> str:
        """Compress multiple chunk annotations into a final summary while preserving details."""
        system_prompt = """You are synthesizing multiple memory annotations into one coherent summary.

Each annotation represents a chunk of a larger conversation. Synthesize them into:
- A unified narrative with all important facts preserved
- Key facts, numbers, and entities from ALL chunks (be exhaustive)
- Important patterns and recurring themes across the full conversation
- All decisions, conclusions, and open questions
- Technical details and specifications that shouldn't be lost

Preserve granularity and specificity across all chunks."""

        # If annotations are still too large, truncate to most recent
        max_chars = 6000 * 4  # Increased from 4000 to ~6000 tokens
        if len(combined_annotations) > max_chars:
            combined_annotations = "...[earlier annotations truncated]...\n\n" + combined_annotations[-max_chars:]
        
        final = await self.llm.generate(
            prompt=f"Synthesize these chunk annotations:\n\n{combined_annotations}",
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1200  # Increased from 1000 to preserve more detail
        )
        return final

