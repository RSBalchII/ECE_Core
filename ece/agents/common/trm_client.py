"""
TRM (Tokenized Reasoning Model) Client

This module provides a client for communicating with the specialized
TRM Service (the "Markovian Thinker") for iterative refinement of thought processes.
"""

import httpx
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging


@dataclass
class TRMConfig:
    """Configuration for TRM client"""

    api_base: str = "http://localhost:8081/v1"  # OpenAI-compatible API base
    model: str = "jamba-reasoning-3b-F16.gguf"  # TRM model name
    timeout: float = 60.0
    max_retries: int = 3
    max_iterations: int = 10
    stability_threshold: float = 0.01


class TRMClient:
    """
    A client for communicating with the specialized TRM Service (the "Markovian Thinker").

    The TRM Service is responsible for iterative refinement of thought processes,
    using a specialized model for critique and refinement tasks.
    """

    def __init__(self, config: Optional[TRMConfig] = None):
        self.config = config or TRMConfig()
        self.client = httpx.AsyncClient(timeout=self.config.timeout)
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def health_check(self) -> bool:
        """Check if the TRM service is available."""
        try:
            # Check models endpoint which is standard in OpenAI-compatible APIs
            response = await self.client.get(
                f"{self.config.api_base.replace('/v1', '')}/v1/models"
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"TRM health check failed: {e}")
            return False

    async def refine_thought(
        self, query: str, current_thought: str, carryover: str = ""
    ) -> str:
        """
        Refine a current thought based on the original query and carryover.

        Args:
            query: The original query or problem statement
            current_thought: The current thought/idea to be refined
            carryover: Previous context or insights to maintain consistency

        Returns:
            The refined thought
        """
        # Construct a prompt that asks the model to refine the thought
        system_message = "You are a reasoning refinement expert. Your task is to improve, clarify, and enhance the thought provided by the user based on the original query. Keep the response focused and relevant to the query."
        user_message = f"Original query: {query}\n\nCarryover context: {carryover}\n\nCurrent thought to refine: {current_thought}\n\nRefined thought:"

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.client.post(
                f"{self.config.api_base}/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "max_tokens": 2048,
                    "temperature": 0.3,  # Lower temperature for more consistent refinement
                },
            )
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                refined_thought = result["choices"][0]["message"]["content"].strip()
                return refined_thought
            else:
                self.logger.error(f"Invalid response format from TRM: {result}")
                return current_thought

        except Exception as e:
            self.logger.error(f"TRM refinement failed: {e}")
            return current_thought  # Return original if refinement fails

    async def critique_thought(self, query: str, thought: str) -> Dict[str, Any]:
        """
        Critique a thought based on the original query.

        Args:
            query: The original query or problem statement
            thought: The thought to be critiqued

        Returns:
            A dictionary containing critique and suggested improvements
        """
        # Construct a prompt that asks the model to critique the thought
        system_message = "You are a reasoning critique expert. Analyze the provided thought against the original query. Identify issues, logical flaws, gaps, and provide specific suggestions for improvement."
        user_message = f"Original query: {query}\n\nThought to critique: {thought}\n\nPlease provide a detailed critique in the following JSON format: {{'valid': boolean, 'issues': [list of issues], 'suggestions': [list of suggestions]}}"

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.client.post(
                f"{self.config.api_base}/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},  # Request JSON response
                },
            )
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                critique_text = result["choices"][0]["message"]["content"].strip()
                try:
                    # Parse the JSON response
                    critique_data = eval(
                        critique_text
                    )  # Note: In production, use json.loads instead of eval
                    # Validate the structure
                    if (
                        "valid" in critique_data
                        and "issues" in critique_data
                        and "suggestions" in critique_data
                    ):
                        return critique_data
                except:
                    self.logger.warning(
                        f"Could not parse critique JSON: {critique_text}"
                    )

            # Return default critique if parsing fails
            return {
                "valid": True,
                "issues": ["Could not parse critique response"],
                "suggestions": ["Review the reasoning approach"],
            }
        except Exception as e:
            self.logger.error(f"TRM critique failed: {e}")
            return {
                "valid": False,
                "issues": [f"Error during critique: {e}"],
                "suggestions": [],
            }

    async def iterative_refinement(
        self, query: str, initial_draft: str, max_iterations: Optional[int] = None
    ) -> str:
        """
        Perform iterative refinement of a thought through multiple TRM calls.

        Args:
            query: The original query or problem statement
            initial_draft: The initial draft to be refined
            max_iterations: Maximum number of refinement iterations (defaults to config)

        Returns:
            The final refined thought after iterative refinement
        """
        max_iterations = max_iterations or self.config.max_iterations
        current_thought = initial_draft
        carryover = ""
        previous_thought = ""

        for iteration in range(max_iterations):
            self.logger.info(f"TRM Iteration {iteration + 1}/{max_iterations}")

            # Critique the current thought
            critique_result = await self.critique_thought(query, current_thought)

            # Check if the thought has stabilized (minimal change from previous iteration)
            if previous_thought:
                # Simple comparison - in practice, this could use more sophisticated similarity measures
                similarity = self._calculate_similarity(
                    previous_thought, current_thought
                )
                if 1 - similarity < self.config.stability_threshold:
                    self.logger.info(
                        f"TRM refinement stabilized at iteration {iteration + 1}"
                    )
                    break

            # Refine the thought based on critique
            refined_thought = await self.refine_thought(
                query, current_thought, carryover
            )

            # Update for next iteration
            previous_thought = current_thought
            current_thought = refined_thought

            # Update carryover with key points from the current thought
            carryover = self._extract_carryover(current_thought)

        return current_thought

    def _calculate_similarity(self, thought1: str, thought2: str) -> float:
        """
        Calculate a simple similarity score between two thoughts.
        This is a basic implementation; a more sophisticated version would use embeddings.
        """
        tokens1 = set(thought1.lower().split())
        tokens2 = set(thought2.lower().split())

        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)

        return len(intersection) / len(union)

    def _extract_carryover(self, thought: str) -> str:
        """
        Extract key points from a thought to carry over to the next iteration.
        This is a simplified implementation that returns the last few sentences.
        """
        sentences = thought.split(".")
        # Take the last 2 sentences as carryover, or the whole thought if it's short
        if len(sentences) <= 3:
            return thought
        else:
            return ".".join(sentences[-3:]) + "."

    async def process_chunk(
        self, query: str, context_chunk: str, carryover: str = ""
    ) -> str:
        """
        Process a single chunk of context through the TRM service.

        Args:
            query: The original query or problem statement
            context_chunk: The chunk of context to process
            carryover: Information to maintain consistency across chunks

        Returns:
            The processed and refined chunk
        """
        # Construct a prompt that asks the model to process the chunk
        system_message = "You are a reasoning processing expert. Your task is to analyze the provided context chunk in relation to the original query and carryover information, then provide a processed, refined, or extended version of the chunk."
        user_message = f"Original query: {query}\n\nCarryover context: {carryover}\n\nContext chunk to process: {context_chunk}\n\nProcessed chunk:"

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.client.post(
                f"{self.config.api_base}/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "max_tokens": 2048,
                    "temperature": 0.4,  # Moderate temperature to balance creativity and consistency
                },
            )
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                processed_chunk = result["choices"][0]["message"]["content"].strip()
                return processed_chunk
            else:
                self.logger.error(f"Invalid response format from TRM: {result}")
                return context_chunk
        except Exception as e:
            self.logger.error(f"TRM chunk processing failed: {e}")
            return context_chunk  # Return original if processing fails
