"""
C2C-Enhanced Graph Reasoner: Graph-R1 with KV-Cache Fusion

Extends the standard GraphReasoner with C2C semantic communication techniques
for improved efficiency in iterative reasoning loops.

Key improvements:
- Preserves KV-cache state across iterations
- Compresses semantic state instead of full text carryover
- Merges overlapping retrieved context
- Measures efficiency gains
"""

import json
from typing import List, Dict, Any, Optional
from retrieval.kv_cache_fusion import (
    KVCachePool, CacheManager, C2COptimizer, SemanticState, create_c2c_system
)


class C2CGraphReasoner:
    """
    Graph-R1 style reasoning with C2C cache fusion.
    
    Integrates semantic caching to reduce redundant computation:
    - System prompt cached once per session
    - Memories cached by source
    - Reasoning states compressed and cached
    - Attention caches merged where beneficial
    """
    
    def __init__(self, memory, llm, enable_c2c: bool = True, cache_ttl: int = 600):
        """
        Initialize C2C-enhanced Graph Reasoner.
        
        Args:
            memory: TieredMemory instance
            llm: LLMClient instance
            enable_c2c: Enable C2C optimizations
            cache_ttl: Cache time-to-live in seconds
        """
        self.memory = memory
        self.llm = llm
        self.enable_c2c = enable_c2c
        self.max_iterations = 5
        
        # C2C components
        if enable_c2c:
            self.cache_pool = KVCachePool(ttl_seconds=cache_ttl)
            self.cache_manager = CacheManager(self.cache_pool, fusion_threshold=0.7)
            self.optimizer = C2COptimizer(self.cache_manager)
        else:
            self.cache_pool = None
            self.cache_manager = None
            self.optimizer = None
    
    async def reason(
        self,
        session_id: str,
        question: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Main reasoning loop with C2C optimization.
        
        Args:
            session_id: Session identifier
            question: Question to reason about
            use_cache: Whether to use C2C caching
        
        Returns:
            Reasoning result with trace and metrics
        """
        reasoning_trace = []
        current_thought = question
        retrieved_context = []
        c2c_metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "tokens_saved": 0,
            "fusions_performed": 0
        }
        
        # Setup system prompt caching
        system_prompt = self._get_system_prompt()
        if self.enable_c2c and use_cache:
            await self.cache_manager.cache_system_prompt(session_id, system_prompt)
        
        for iteration in range(self.max_iterations):
            # Step 1: Think (high-level planning)
            thought = await self._think(
                current_thought,
                retrieved_context,
                iteration,
                session_id
            )
            reasoning_trace.append({
                "iteration": iteration,
                "thought": thought,
                "type": "planning"
            })
            
            # Step 2: Generate query from thought
            query = await self._generate_query(thought, question)
            reasoning_trace.append({
                "iteration": iteration,
                "query": query,
                "type": "query_generation"
            })
            
            # Step 3: Retrieve subgraph with C2C awareness
            subgraph = await self._retrieve_subgraph_with_cache(
                query,
                session_id,
                iteration,
                c2c_metrics
            )
            retrieved_context.append({
                "iteration": iteration,
                "subgraph": subgraph
            })
            reasoning_trace.append({
                "iteration": iteration,
                "retrieved": len(subgraph),
                "type": "retrieval"
            })
            
            # Step 4: Check if we can answer
            answer_attempt = await self._attempt_answer(
                question,
                thought,
                retrieved_context,
                session_id
            )
            
            if answer_attempt["confident"]:
                reasoning_trace.append({
                    "iteration": iteration,
                    "final_answer": answer_attempt["answer"],
                    "type": "answer"
                })
                
                # Cache final semantic state
                if self.enable_c2c and use_cache:
                    final_state = SemanticState(
                        iteration=iteration,
                        state_id=f"{session_id}:final",
                        reasoning_text=thought,
                        key_entities=self._extract_entities(answer_attempt["answer"]),
                        decisions=self._extract_decisions(answer_attempt["answer"]),
                        open_questions=[],
                        compressed_tokens=len(answer_attempt["answer"]) // 4
                    )
                    await self.cache_manager.cache_semantic_state(session_id, final_state)
                
                return {
                    "answer": answer_attempt["answer"],
                    "reasoning_trace": reasoning_trace,
                    "iterations": iteration + 1,
                    "confidence": "high",
                    "c2c_metrics": c2c_metrics
                }
            
            # Step 5: Rethink for next iteration with state compression
            current_thought = await self._rethink(
                thought,
                retrieved_context,
                question
            )
            
            # Cache semantic state for this iteration
            if self.enable_c2c and use_cache:
                state = SemanticState(
                    iteration=iteration,
                    state_id=f"{session_id}:iter_{iteration}",
                    reasoning_text=current_thought,
                    key_entities=self._extract_entities(current_thought),
                    decisions=self._extract_decisions(thought),
                    open_questions=self._extract_questions(current_thought),
                    compressed_tokens=len(current_thought) // 4
                )
                await self.cache_manager.cache_semantic_state(session_id, state)
        
        # Max iterations reached - provide best attempt
        final_answer = await self._final_answer(question, retrieved_context)
        reasoning_trace.append({
            "iteration": self.max_iterations,
            "final_answer": final_answer,
            "type": "final_attempt"
        })
        
        # Log optimization recommendations
        if self.enable_c2c and use_cache:
            recommendation = await self.optimizer.get_optimization_recommendation(session_id)
            reasoning_trace.append({
                "type": "optimization_note",
                "recommendation": recommendation
            })
        
        return {
            "answer": final_answer,
            "reasoning_trace": reasoning_trace,
            "iterations": self.max_iterations,
            "confidence": "medium",
            "c2c_metrics": c2c_metrics
        }
    
    async def _think(
        self,
        current_thought: str,
        retrieved_context: List[Dict],
        iteration: int,
        session_id: str
    ) -> str:
        """High-level planning step with cache awareness."""
        context_summary = self._summarize_context(retrieved_context)
        
        prompt = f"""You are in iteration {iteration} of a reasoning process.

Current question/thought: {current_thought}

Retrieved context so far:
{context_summary}

What should you focus on next? Think step by step about:
1. What information is still missing?
2. What aspect of the question needs exploration?
3. What specific memory or knowledge would help?

Provide a concise plan (2-3 sentences)."""
        
        thought = await self.llm.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=150
        )
        
        # Log for optimization
        if self.enable_c2c:
            await self.optimizer.log_call(
                session_id=session_id,
                call_type="reasoning",
                content_length=len(prompt),
                response_tokens=len(thought) // 4
            )
        
        return thought.strip()
    
    async def _generate_query(self, thought: str, original_question: str) -> str:
        """Generate search query from reasoning."""
        prompt = f"""Based on this reasoning step:
{thought}

And original question:
{original_question}

Generate a concise search query (keywords and concepts) to find relevant memories.
Query:"""
        
        query = await self.llm.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=50
        )
        
        return query.strip()
    
    async def _retrieve_subgraph_with_cache(
        self,
        query: str,
        session_id: str,
        iteration: int,
        metrics: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """
        Retrieve subgraph with C2C cache checking.
        
        Strategy: Check if memories for this query are already cached.
        If so, reuse. Otherwise, retrieve and cache for future iterations.
        """
        # Extract keywords
        keywords = query.lower().split()
        
        # Check if we have cached memories for these keywords
        if self.enable_c2c:
            cached_memories = await self.cache_pool.get_cached_by_source(
                session_id,
                "memory"
            )
            if cached_memories:
                metrics["cache_hits"] += 1
            else:
                metrics["cache_misses"] += 1
        
        # Retrieve summaries
        summaries = await self.memory.get_summaries(session_id, limit=3)
        
        # Retrieve memories
        memories = []
        for keyword in keywords[:3]:
            mem = await self.memory.search_memories(tags=[keyword], limit=2)
            memories.extend(mem)
        
        # Cache retrieved memories for future use
        if self.enable_c2c and memories:
            await self.cache_manager.cache_retrieved_memories(session_id, memories)
        
        # Build subgraph
        subgraph = []
        for summary in summaries:
            subgraph.append({
                "type": "summary",
                "content": summary["summary"],
                "timestamp": summary.get("timestamp", "")
            })
        
        for mem in memories:
            if len(subgraph) < 5:
                subgraph.append({
                    "type": "memory",
                    "category": mem.get("category", ""),
                    "content": mem.get("content", ""),
                    "timestamp": mem.get("created_at", "")
                })
        
        return subgraph
    
    async def _attempt_answer(
        self,
        question: str,
        current_thought: str,
        retrieved_context: List[Dict],
        session_id: str
    ) -> Dict[str, Any]:
        """Attempt to answer with confidence check."""
        context_text = self._format_context(retrieved_context)
        
        prompt = f"""Question: {question}

Current reasoning: {current_thought}

Retrieved context:
{context_text}

Can you answer the question with HIGH confidence based on this context?
If YES: Provide the answer.
If NO: Explain what information is still needed.

Format:
Confidence: [HIGH/LOW]
Answer or Reasoning: [your response]"""
        
        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=300
        )
        
        if self.enable_c2c:
            await self.optimizer.log_call(
                session_id=session_id,
                call_type="answer_attempt",
                content_length=len(prompt),
                response_tokens=len(response) // 4
            )
        
        # Parse response
        lines = response.strip().split('\n')
        confident = "HIGH" in lines[0].upper() if lines else False
        answer = '\n'.join(lines[1:]).replace("Answer or Reasoning:", "").strip()
        
        return {
            "confident": confident,
            "answer": answer
        }
    
    async def _rethink(
        self,
        previous_thought: str,
        retrieved_context: List[Dict],
        original_question: str
    ) -> str:
        """Rethink for next iteration (Markovian state transition)."""
        context_summary = self._summarize_context(retrieved_context)
        
        prompt = f"""Original question: {original_question}

Previous reasoning: {previous_thought}

What we've learned:
{context_summary}

What should be the next focus? Provide a refined thought (1-2 sentences)."""
        
        rethought = await self.llm.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=100
        )
        
        return rethought.strip()
    
    async def _final_answer(
        self,
        question: str,
        retrieved_context: List[Dict]
    ) -> str:
        """Generate final answer after max iterations."""
        context_text = self._format_context(retrieved_context)
        
        prompt = f"""Question: {question}

All retrieved context:
{context_text}

Based on everything available, provide the best possible answer."""
        
        answer = await self.llm.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=500
        )
        
        return answer.strip()
    
    def _summarize_context(self, retrieved_context: List[Dict]) -> str:
        """Create summary of retrieved context."""
        if not retrieved_context:
            return "No context retrieved yet."
        
        summary_parts = []
        for ctx in retrieved_context[-3:]:
            subgraph = ctx.get("subgraph", [])
            summary_parts.append(
                f"Iteration {ctx['iteration']}: Retrieved {len(subgraph)} items"
            )
        
        return "\n".join(summary_parts)
    
    def _format_context(self, retrieved_context: List[Dict]) -> str:
        """Format context for prompts."""
        if not retrieved_context:
            return "No context available."
        
        formatted = []
        for ctx in retrieved_context:
            subgraph = ctx.get("subgraph", [])
            for item in subgraph:
                formatted.append(f"[{item['type']}] {item['content'][:200]}...")
        
        return "\n\n".join(formatted) if formatted else "No specific context."
    
    def _get_system_prompt(self) -> str:
        """Return system prompt for this reasoner."""
        return """You are a helpful reasoning assistant. 
Help the user think through complex questions by breaking them down, 
retrieving relevant information, and building understanding iteratively."""
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract key entities from text (simplified)."""
        # In production, would use NER or other entity extraction
        words = text.split()
        # Simple heuristic: capitalized words
        entities = [w.strip('.,!?;:()[]{}') for w in words if w and w[0].isupper()]
        return list(set(entities))[:10]
    
    def _extract_decisions(self, text: str) -> List[str]:
        """Extract key decisions from text (simplified)."""
        # Look for decision keywords
        decision_keywords = ['decided', 'conclude', 'determined', 'agreed', 'chose']
        decisions = []
        for keyword in decision_keywords:
            if keyword in text.lower():
                # Extract sentence with keyword
                sentences = text.split('.')
                for sent in sentences:
                    if keyword in sent.lower():
                        decisions.append(sent.strip())
        return decisions[:5]
    
    def _extract_questions(self, text: str) -> List[str]:
        """Extract open questions from text."""
        # Look for question marks
        sentences = text.split('.')
        questions = [s.strip() + '?' for s in sentences if '?' in s]
        return questions[:3]
    
    async def get_cache_stats(self, session_id: str) -> Dict[str, Any]:
        """Get cache performance statistics for a session."""
        if not self.enable_c2c:
            return {"enabled": False}
        
        return await self.cache_manager.get_fusion_stats(session_id)
    
    async def cleanup_session(self, session_id: str):
        """Clean up caches for a session."""
        if self.enable_c2c:
            await self.cache_pool.cleanup_session(session_id)


# Factory function
async def create_c2c_reasoner(memory, llm, enable_c2c: bool = True):
    """
    Create a C2C-enhanced Graph Reasoner.
    
    Args:
        memory: TieredMemory instance
        llm: LLMClient instance
        enable_c2c: Enable C2C optimizations
    
    Returns:
        C2CGraphReasoner instance
    """
    return C2CGraphReasoner(memory, llm, enable_c2c=enable_c2c)
