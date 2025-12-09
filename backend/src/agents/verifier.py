"""
Verifier Agent (Empirical Distrust)
Implements System 2 verification loop for claims.
"""
from typing import List, Dict, Any, Optional
from src.llm import LLMClient
from src.memory import TieredMemory
import logging
import json

logger = logging.getLogger(__name__)

class VerifierAgent:
    """
    Verifier Agent implements 'Empirical Distrust'.
    It verifies claims by seeking primary source evidence and calculating provenance entropy.
    """
    
    def __init__(self, memory: TieredMemory, llm: LLMClient):
        self.memory = memory
        self.llm = llm
        
    async def verify_claim(self, claim: str, context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Verify a specific claim against provided context and primary sources.
        Returns verification result with score and evidence.
        """
        # 1. Identify key facts in claim
        facts = await self._extract_facts(claim)
        
        # 2. Check evidence for each fact
        verified_facts = []
        overall_score = 0.0
        
        for fact in facts:
            evidence = await self._find_evidence(fact, context)
            fact_score = self._calculate_provenance_score(evidence)
            verified_facts.append({
                "fact": fact,
                "evidence": evidence,
                "score": fact_score,
                "verified": fact_score > 0.7
            })
            overall_score += fact_score
            
        avg_score = overall_score / len(facts) if facts else 0.0
        
        return {
            "claim": claim,
            "verified": avg_score > 0.7,
            "score": avg_score,
            "details": verified_facts
        }

    async def _extract_facts(self, claim: str) -> List[str]:
        """Extract atomic facts from claim using LLM."""
        prompt = f"""Extract atomic, verifiable facts from this claim:
"{claim}"

Return as JSON list of strings."""
        
        try:
            response = await self.llm.generate(prompt, temperature=0.1)
            # Simple parsing attempt
            if "[" in response:
                start = response.find("[")
                end = response.rfind("]") + 1
                return json.loads(response[start:end])
            return [claim]
        except Exception:
            return [claim]

    async def _find_evidence(self, fact: str, context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find supporting evidence in context."""
        evidence = []
        # Simple keyword matching for now, could be semantic
        fact_terms = set(fact.lower().split())
        
        for item in context:
            content = item.get("content", "").lower()
            # Check overlap
            if any(term in content for term in fact_terms if len(term) > 4):
                evidence.append(item)
                
        return evidence

    def _calculate_provenance_score(self, evidence: List[Dict[str, Any]]) -> float:
        """
        Calculate score based on source type.
        Primary sources (code, logs) > Secondary (docs) > Tertiary (chat).
        """
        if not evidence:
            return 0.0
            
        score_sum = 0.0
        for item in evidence:
            # Determine source type from metadata
            meta = item.get("metadata", {})
            source = meta.get("source", "unknown")
            category = item.get("category", "unknown")
            
            weight = 0.5 # Default
            
            if category == "code" or source.endswith(".py") or source.endswith(".log"):
                weight = 1.0 # Primary
            elif category == "doc" or source.endswith(".md"):
                weight = 0.8 # Secondary
            elif category == "chat":
                weight = 0.4 # Tertiary/Hearsay
                
            score_sum += weight
            
        # Normalize (diminishing returns)
        return min(1.0, score_sum)
