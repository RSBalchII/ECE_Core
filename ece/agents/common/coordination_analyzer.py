"""
Coordination Analyzer for Multi-Agent Systems

This module implements analysis of coordination patterns in multi-agent interactions
based on the research findings from "Emergent Coordination in Multi-Agent Language Models".
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class CoordinationAnalyzer:
    """
    Analyze coordination patterns in multi-agent interactions based on information theory concepts.
    """
    
    @staticmethod
    def measure_synergy(results: List[str]) -> float:
        """
        Measure the synergy between different thinker results.
        This metric evaluates how much more valuable the combined insights are
        compared to the sum of individual insights.
        """
        if len(results) < 2:
            return 0.0
        
        # Convert results to TF-IDF vectors
        try:
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform(results)
            
            # Calculate pairwise similarities
            similarities = cosine_similarity(tfidf_matrix)
            
            # Calculate diversity (1 - average similarity)
            # Lower average similarity means higher diversity/synergy
            upper_triangle = similarities[np.triu_indices_from(similarities, k=1)]
            avg_similarity = np.mean(upper_triangle) if len(upper_triangle) > 0 else 0
            
            # Synergy is inversely related to similarity - more diverse results = higher synergy
            synergy_score = 1.0 - avg_similarity
            return max(0.0, min(1.0, synergy_score))  # Normalize to [0, 1]
        except:
            # Fallback if vectorization fails
            return 0.5  # Neutral score
    
    @staticmethod
    def measure_diversity(results: List[str]) -> float:
        """
        Measure the diversity of approaches taken by different thinkers.
        """
        if len(results) < 2:
            return 0.0
        
        try:
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform(results)
            
            # Calculate pairwise distances
            similarities = cosine_similarity(tfidf_matrix)
            distances = 1 - similarities
            
            # Average distance between all pairs
            upper_triangle = distances[np.triu_indices_from(distances, k=1)]
            avg_distance = np.mean(upper_triangle) if len(upper_triangle) > 0 else 0
            
            return max(0.0, min(1.0, avg_distance))  # Normalize to [0, 1]
        except:
            return 0.5  # Neutral score
    
    @staticmethod
    def measure_complementarity(results: List[str], original_prompt: str) -> float:
        """
        Measure how complementary the thinkers' responses are to the original prompt.
        """
        if not results:
            return 0.0
        
        try:
            # Vectorize both the original prompt and results
            all_texts = [original_prompt] + results
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            
            # Calculate how much each result contributes information not in the prompt
            prompt_vector = tfidf_matrix[0]  # First is the prompt
            result_vectors = tfidf_matrix[1:]  # Rest are results
            
            complementarity_scores = []
            for result_vector in result_vectors:
                # Calculate similarity between prompt and result
                similarity = cosine_similarity(prompt_vector, result_vector)[0][0]
                # Complementarity is 1 - similarity (less similar = more complementary)
                complementarity_scores.append(1.0 - similarity)
            
            return np.mean(complementarity_scores) if complementarity_scores else 0.0
        except:
            return 0.5  # Neutral score


class ThinkerCoordinator:
    """
    Coordinates thinking processes based on the research on emergent coordination.
    """
    
    def __init__(self):
        self.analyzer = CoordinationAnalyzer()
        self.logger = logging.getLogger(__name__)
    
    def assign_thinker_personas(self) -> Dict[str, str]:
        """
        Assign detailed personas to each thinker based on research findings.
        """
        personas = {
            "OptimistThinker": (
                "You are Elena, a seasoned innovation consultant with 15 years of experience. "
                "You approach problems with enthusiasm and look for opportunities in challenges. "
                "Your background in design thinking helps you identify creative solutions and "
                "positive outcomes that others might miss."
            ),
            "PessimistThinker": (
                "You are Marcus, a risk management expert who has worked in finance for 20 years. "
                "You focus on identifying potential pitfalls and risks in proposed solutions. "
                "Your experience includes crisis management and contingency planning. "
                "Consider the negative outcomes and obstacles others might not see."
            ),
            "AnalyticalThinker": (
                "You are Priya, a data scientist with expertise in statistical analysis. "
                "You approach problems methodically, requiring evidence and logical reasoning "
                "for all conclusions. You focus on data-driven insights and measurable outcomes."
            ),
            "CreativeThinker": (
                "You are Alex, an award-winning creative director with experience across "
                "multiple industries. You think outside conventional approaches and "
                "generate innovative solutions. You look for unique connections and "
                "unusual perspectives on problems."
            ),
            "PragmaticThinker": (
                "You are Jamie, a project manager with expertise in implementation. "
                "You focus on practical, executable solutions that can be implemented "
                "with available resources. You consider constraints and feasibility."
            ),
            "StrategicThinker": (
                "You are Sarah, a former military strategist turned business consultant. "
                "You consider long-term implications and big-picture consequences of decisions. "
                "You think in terms of goals, resources, and competitive positioning."
            ),
            "EthicalThinker": (
                "You are David, an ethics professor with expertise in moral philosophy. "
                "You evaluate solutions based on ethical implications and fairness. "
                "Consider the impact on different stakeholders and ethical principles."
            )
        }
        return personas
    
    def generate_thinker_instructions(self, thinker_name: str, other_thinkers_info: List[Dict[str, str]]) -> str:
        """
        Generate instructions for a thinker that incorporates Theory of Mind considerations.
        
        Args:
            thinker_name: Name of the current thinker
            other_thinkers_info: List of dicts with 'name' and 'role_description' keys
        """
        # Create a description of other thinkers
        other_thinkers_desc = ""
        if other_thinkers_info:
            other_thinkers_desc = "Other thinkers in this system have the following roles: "
            other_thinkers_desc += ", ".join([
                f"{thinker['name']} ({thinker['role_description']})" 
                for thinker in other_thinkers_info 
                if thinker['name'] != thinker_name
            ])
            other_thinkers_desc += ". "
        else:
            other_thinkers_desc = ""
        
        to_m_instruction = (
            f"{other_thinkers_desc}"
            f"Consider how your analysis might complement or contrast with other thinkers in the system. "
            f"Think about what unique perspective your role brings to this problem. "
            f"If another thinker might analyze risks, focus on opportunities. "
            f"If others focus on details, consider high-level patterns. "
            f"How might your expertise fill a gap in the collective analysis of this problem?"
        )
        
        return to_m_instruction


# Example usage:
# coordinator = ThinkerCoordinator()
# personas = coordinator.assign_thinker_personas()
# to_m_instruction = coordinator.generate_thinker_instructions(
#     "OptimistThinker", 
#     [{"name": "PessimistThinker", "role_description": "Risk identification"}]
# )