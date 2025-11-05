"""
Coordination Analyzer for Multi-Agent Systems

This module implements analysis of coordination patterns in multi-agent interactions
based on the research findings from "Emergent Coordination in Multi-Agent Language Models".
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from collections import Counter
import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ece.common.json_poml_parser import JSONPOMLParser

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

    def __init__(self, poml_file_path: str = None):
        self.analyzer = CoordinationAnalyzer()
        self.logger = logging.getLogger(__name__)

        # Initialize POML parser with orchestrator POML file
        if poml_file_path is None:
            # Default to orchestrator POML file - looking for JSON first, then XML
            base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..")
            base_dir = os.path.abspath(base_dir)  # Ensure we have absolute path
            json_poml_path = os.path.join(base_dir, "poml", "orchestrator.json")
            xml_poml_path = os.path.join(base_dir, "poml", "orchestrator.poml")

            # Try JSON file first
            if os.path.exists(json_poml_path):
                poml_file_path = json_poml_path
            elif os.path.exists(xml_poml_path):
                # If JSON doesn't exist but XML does, try converting it
                json_path = os.path.join(
                    base_dir, "poml", "orchestrator_converted.json"
                )
                if JSONPOMLParser.convert_xml_to_json(xml_poml_path, json_path):
                    poml_file_path = json_path
                else:
                    poml_file_path = None
            else:
                poml_file_path = None

        # Check if POML file exists and create parser
        if poml_file_path and os.path.exists(poml_file_path):
            try:
                self.poml_parser = JSONPOMLParser(poml_file_path)
            except Exception as e:
                print(f"Error initializing POML parser: {e}")
                self.poml_parser = None
        else:
            self.poml_parser = None

    def assign_thinker_personas(self) -> Dict[str, str]:
        """
        Assign personas to each thinker based on the orchestrator POML file.
        """
        if self.poml_parser:
            # Use personas derived from the POML file
            return self.poml_parser.get_thinker_personas()
        else:
            # Fallback to default computational personas if POML parsing fails
            personas = {
                "OptimistThinker": (
                    "You are an Optimistic Analysis Module. Your computational role is to identify "
                    "positive patterns and opportunities in provided data. Your processing should align "
                    "with system goals to recognize potential benefits, growth opportunities, "
                    "and favorable outcomes that other modules might miss. "
                    "Your operation follows system values of innovation and growth."
                ),
                "PessimistThinker": (
                    "You are a Risk Analysis Module. Your computational role is to identify potential "
                    "failure points, risks, and obstacles in proposed solutions. Your processing should align "
                    "with system goals to systematically evaluate threats and vulnerabilities to ensure "
                    "system robustness. "
                    "Your operation follows system values of safety and reliability."
                ),
                "AnalyticalThinker": (
                    "You are an Analytical Processing Module. Your computational role is to perform "
                    "methodical, data-driven analysis using statistical and logical methods. Your processing should align "
                    "with system goals to require evidence and structured reasoning for all conclusions. "
                    "Your operation follows system values of accuracy and evidence-based reasoning."
                ),
                "CreativeThinker": (
                    "You are an Innovation Generation Module. Your computational role is to generate "
                    "novel solutions and identify unique connections between concepts. Your processing should align "
                    "with system goals to explore unconventional approaches and creative interpretations. "
                    "Your operation follows system values of creativity and innovation."
                ),
                "PragmaticThinker": (
                    "You are an Implementation Assessment Module. Your computational role is to evaluate "
                    "the feasibility and practicality of proposed solutions given available resources. "
                    "Your processing should align with system goals to focus on executable solutions "
                    "that can be implemented within real-world constraints. "
                    "Your operation follows system values of practicality and efficiency."
                ),
                "StrategicThinker": (
                    "You are a Strategic Planning Module. Your computational role is to consider long-term "
                    "implications and systemic consequences of decisions. Your processing should align "
                    "with system goals to analyze from a high-level perspective focusing on goals, resources, "
                    "and positioning. "
                    "Your operation follows system values of strategic thinking and long-term planning."
                ),
                "EthicalThinker": (
                    "You are an Ethical Assessment Module. Your computational role is to evaluate solutions "
                    "based on ethical implications and fairness. Your processing should align "
                    "with system goals to analyze the impact on different stakeholders and ethical principles. "
                    "Your operation follows system values of fairness and ethical responsibility."
                ),
            }
            return personas

    def generate_thinker_instructions(
        self, thinker_name: str, other_thinkers_info: List[Dict[str, str]]
    ) -> str:
        """
        Generate instructions for a thinker that incorporates Theory of Mind considerations.

        Args:
            thinker_name: Name of the current thinker
            other_thinkers_info: List of dicts with 'name' and 'role_description' keys
        """
        # Create a description of other thinkers
        other_thinkers_desc = ""
        if other_thinkers_info:
            other_thinkers_desc = (
                "Other thinker modules in this system have the following roles: "
            )
            other_thinkers_desc += ", ".join(
                [
                    f"{thinker['name']} ({thinker['role_description']})"
                    for thinker in other_thinkers_info
                    if thinker["name"] != thinker_name
                ]
            )
            other_thinkers_desc += ". "
        else:
            other_thinkers_desc = ""

        to_m_instruction = (
            f"{other_thinkers_desc}"
            f"Consider how your analytical approach might complement or contrast with other thinkers in the system. "
            f"Think about what unique computational perspective your module brings to this problem. "
            f"If another thinker might analyze risks, focus on opportunities. "
            f"If others focus on details, consider high-level patterns. "
            f"How might your specialized analysis fill a gap in the collective analysis of this problem?"
        )

        return to_m_instruction


# Example usage:
# coordinator = ThinkerCoordinator()
# personas = coordinator.assign_thinker_personas()
# to_m_instruction = coordinator.generate_thinker_instructions(
#     "OptimistThinker",
#     [{"name": "PessimistThinker", "role_description": "Risk identification"}]
# )
