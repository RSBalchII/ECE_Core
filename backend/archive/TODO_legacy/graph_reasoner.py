"""
Graph-R1 Reasoning Layer for ECE_Core
Implements: think → generate query → retrieve subgraph → rethink
Based on Graph-R1 paper: arxiv.org/abs/2507.21892
"""
import json
from typing import List, Dict, Any, Optional
from llm_client import LLMClient
from memory import TieredMemory

class GraphReasoner:
    """
    Graph-R1 style reasoning over memory graph.
    Implements iterative "think-query-retrieve-rethink" cycle.
    """
    
    def __init__(self, memory: TieredMemory, llm: LLMClient):
        self.memory = memory
        self.llm = llm
        self.max_iterations = 5  # Markovian thinking: small fixed iterations
    
    async def reason(self, session_id: str, question: str) -> Dict[str, Any]:
        """
        Main reasoning loop: think → query → retrieve → rethink
        Returns final answer with reasoning trace
        """
        reasoning_trace = []
        current_thought = question
        retrieved_context = []
        
        for iteration in range(self.max_iterations):
            # Step 1: Think (high-level planning)
            thought = await self._think(current_thought, retrieved_context, iteration)
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
            
            # Step 3: Retrieve subgraph (from SQLite memories)
            subgraph = await self._retrieve_subgraph(query, session_id)
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
                retrieved_context
            )
            
            if answer_attempt["confident"]:
                reasoning_trace.append({
                    "iteration": iteration,
                    "final_answer": answer_attempt["answer"],
                    "type": "answer"
                })
                return {
                    "answer": answer_attempt["answer"],
                    "reasoning_trace": reasoning_trace,
                    "iterations": iteration + 1,
                    "confidence": "high"
                }
            
            # Step 5: Rethink for next iteration
            current_thought = await self._rethink(
                thought, 
                retrieved_context, 
                question
            )
        
        # Max iterations reached - provide best attempt
        final_answer = await self._final_answer(question, retrieved_context)
        reasoning_trace.append({
            "iteration": self.max_iterations,
            "final_answer": final_answer,
            "type": "final_attempt"
        })
        
        return {
            "answer": final_answer,
            "reasoning_trace": reasoning_trace,
            "iterations": self.max_iterations,
            "confidence": "medium"
        }
    
    async def _think(self, current_thought: str, retrieved_context: List[Dict], iteration: int) -> str:
        """
        High-level planning step.
        Like HRM's abstract planning module.
        """
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
        
        return thought.strip()
    
    async def _generate_query(self, thought: str, original_question: str) -> str:
        """
        Generate specific query to retrieve relevant memories.
        """
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
    
    async def _retrieve_subgraph(self, query: str, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories from SQLite.
        This simulates subgraph retrieval from knowledge graph.
        """
        # Extract potential categories and tags from query
        keywords = query.lower().split()
        
        # Search summaries
        summaries = await self.memory.get_summaries(session_id, limit=3)
        
        # Search structured memories (if any)
        memories = []
        for keyword in keywords[:3]:  # Limit to prevent too broad search
            mem = await self.memory.search_memories(tags=[keyword], limit=2)
            memories.extend(mem)
        
        # Combine results
        subgraph = []
        for summary in summaries:
            subgraph.append({
                "type": "summary",
                "content": summary["summary"],
                "timestamp": summary["timestamp"]
            })
        
        for mem in memories:
            if len(subgraph) < 5:  # Limit total retrieved
                subgraph.append({
                    "type": "memory",
                    "category": mem["category"],
                    "content": mem["content"],
                    "timestamp": mem["timestamp"]
                })
        
        return subgraph
    
    async def _attempt_answer(
        self, 
        question: str, 
        current_thought: str, 
        retrieved_context: List[Dict]
    ) -> Dict[str, Any]:
        """
        Attempt to answer based on current knowledge.
        Returns confidence and answer.
        """
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
        """
        Rethink based on what we've learned.
        Markovian: carry forward only essential state (textual summary).
        """
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
    
    async def _final_answer(self, question: str, retrieved_context: List[Dict]) -> str:
        """
        Generate final answer after max iterations.
        """
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
        """Create concise summary of retrieved context."""
        if not retrieved_context:
            return "No context retrieved yet."
        
        summary_parts = []
        for ctx in retrieved_context[-3:]:  # Last 3 iterations
            subgraph = ctx.get("subgraph", [])
            summary_parts.append(
                f"Iteration {ctx['iteration']}: Retrieved {len(subgraph)} items"
            )
        
        return "\n".join(summary_parts)
    
    def _format_context(self, retrieved_context: List[Dict]) -> str:
        """Format all retrieved context for prompts."""
        if not retrieved_context:
            return "No context available."
        
        formatted = []
        for ctx in retrieved_context:
            subgraph = ctx.get("subgraph", [])
            for item in subgraph:
                formatted.append(f"[{item['type']}] {item['content'][:200]}...")
        
        return "\n\n".join(formatted) if formatted else "No specific context."


class MarkovianReasoner:
    """
    Simpler Markovian-style reasoning without graph retrieval.
    Just: think → summarize → repeat with small context window.
    """
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.max_chunks = 5
    
    async def reason(self, task: str, initial_context: str = "") -> str:
        """
        Chunked reasoning with textual carryover.
        Each chunk processes only previous summary + current task.
        """
        carryover = initial_context
        
        for chunk in range(self.max_chunks):
            # Process one reasoning chunk
            chunk_result = await self._process_chunk(task, carryover, chunk)
            
            # Check if task complete
            if chunk_result["complete"]:
                return chunk_result["answer"]
            
            # Carry forward only summary (Markovian property)
            carryover = chunk_result["summary"]
        
        # Final synthesis
        final = await self._synthesize(task, carryover)
        return final
    
    async def _process_chunk(
        self, 
        task: str, 
        carryover: str, 
        chunk_num: int
    ) -> Dict[str, Any]:
        """
        Process one reasoning chunk.
        Small context window: task + previous summary only.
        """
        prompt = f"""Task: {task}

Previous reasoning:
{carryover if carryover else 'Starting fresh.'}

Chunk {chunk_num+1}/{self.max_chunks}:
1. What's one key step toward solving this?
2. Is the task complete? (YES/NO)
3. Summary for next chunk (if incomplete):

Your response:"""
        
        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.4,
            max_tokens=300
        )
        
        # Simple parsing
        lines = response.strip().split('\n')
        complete = any("YES" in line.upper() for line in lines[:5])
        
        return {
            "complete": complete,
            "answer": response if complete else None,
            "summary": response  # Entire response becomes carryover
        }
    
    async def _synthesize(self, task: str, final_carryover: str) -> str:
        """Final synthesis after all chunks."""
        prompt = f"""Task: {task}

Reasoning completed:
{final_carryover}

Provide final answer:"""
        
        answer = await self.llm.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=400
        )
        
        return answer.strip()
