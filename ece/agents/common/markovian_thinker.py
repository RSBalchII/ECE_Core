"""
Implementation of the Markovian Thinker as described in the research paper.
This enables extremely long and complete reasoning by using fixed-size chunks
with textual carryover state between chunks.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple
from xml.etree import ElementTree as ET
import json

import httpx
from pydantic import BaseModel, Field

from utcp.utcp_client import UtcpClient
from utcp.data.tool import Tool
from ece.common.token_utils import count_tokens, truncate_text_to_tokens


logger = logging.getLogger(__name__)


class MarkovianConfig(BaseModel):
    """
    Configuration for Markovian Thinking implementation.
    """

    thinking_context_size: int = 8192  # Size of each chunk (C in the paper)
    markovian_state_size: int = 4096  # Size of carryover tokens (m in the paper)
    iteration_cap: int = 5  # Maximum number of chunks (I in the paper)
    temperature: float = 0.6  # Temperature for generation
    eos_token_id: Optional[int] = None  # End of sequence token ID
    max_retries: int = 3  # Maximum number of retries for API calls
    api_base: str = "http://localhost:8080/v1"  # Default API base
    model: str = "jamba-reasoning-3b-F16.gguf"  # Default model


class MarkovianThinker:
    """
    Implements the Markovian Thinking paradigm as described in the research paper.

    The Markovian Thinker enables extremely long reasoning by:
    1. Processing reasoning in fixed-size chunks
    2. Resetting context at chunk boundaries
    3. Using a textual carryover state to maintain reasoning thread
    """

    def __init__(self, config: MarkovianConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=60.0)

    async def markovian_reasoning_loop(
        self, initial_query: str, context: str = ""
    ) -> str:
        """
        Execute the Markovian reasoning loop as described in the paper.

        Args:
            initial_query: The initial question or problem to reason about
            context: Additional context to include with the query

        Returns:
            The final response after completing all reasoning chunks
        """
        logger.info(f"Starting Markovian reasoning for: {initial_query[:100]}...")

        # Construct the initial query with context
        if context:
            query = f"Context: {context}\n\nQuery: {initial_query}"
        else:
            query = initial_query

        # Current prompt starts with the query
        prompt = query
        trace_ids = []  # List of generated token IDs across chunks

        # Process chunks up to the iteration cap
        for iteration in range(self.config.iteration_cap):
            # Calculate how many new tokens we can generate in this chunk
            max_new_tokens = (
                self.config.thinking_context_size
                if iteration == 0
                else self.config.thinking_context_size
                - self.config.markovian_state_size
            )

            try:
                logger.info(
                    f"Processing chunk {iteration + 1}/{self.config.iteration_cap}"
                )

                # Generate response for this chunk
                response_text = await self._generate_chunk(
                    prompt=prompt, max_new_tokens=max_new_tokens
                )

                # Add the generated tokens to our trace
                trace_ids.extend(response_text)

                # Check if we reached the end of sequence
                if (
                    self.config.eos_token_id
                    and self.config.eos_token_id in response_text
                ):
                    logger.info("EOS token found, stopping reasoning loop")
                    break

                # If this is the first chunk, extract the first 100 tokens to fold into query
                if iteration == 0:
                    first_100_tokens = response_text[:100]
                    # Update the query with these tokens
                    query += "".join(first_100_tokens)

                # Prepare next prompt using the last m tokens as carryover
                carryover_tokens = response_text[-self.config.markovian_state_size :]
                prompt = query + "".join(carryover_tokens)

            except Exception as e:
                logger.error(f"Error in chunk {iteration + 1}: {str(e)}")
                if iteration >= self.config.max_retries:
                    # If we've exhausted retries, return what we have
                    break
                continue  # Try again

        # Combine all the generated text from the trace
        final_response = "".join(trace_ids)
        logger.info(
            f"Markovian reasoning completed, total tokens: {len(final_response)}"
        )

        return final_response

    async def _generate_chunk(self, prompt: str, max_new_tokens: int) -> str:
        """
        Generate a single chunk of reasoning using the configured model.
        """
        # Prepare the messages for the API call
        messages = [
            {
                "role": "system",
                "content": "You are a helpful reasoning assistant. Think step by step in a structured way. Be thorough but concise in each chunk.",
            },
            {"role": "user", "content": prompt},
        ]

        for attempt in range(self.config.max_retries):
            try:
                # Make an async request to the configured LLM API
                response = await self.client.post(
                    f"{self.config.api_base}/chat/completions",
                    json={
                        "model": self.config.model,
                        "messages": messages,
                        "max_tokens": max_new_tokens,
                        "temperature": self.config.temperature,
                        "stream": False,
                    },
                )

                # Check if the request was successful
                if response.status_code == 200:
                    data = response.json()

                    # Extract the generated text
                    if "choices" in data and len(data["choices"]) > 0:
                        generated_text = data["choices"][0]["message"]["content"]
                        return generated_text
                    else:
                        raise Exception(f"Unexpected response format: {data}")
                else:
                    logger.warning(
                        f"API call failed with status {response.status_code}: {response.text}"
                    )

            except httpx.RequestError as e:
                logger.warning(f"Request error (attempt {attempt + 1}): {str(e)}")
                if attempt == self.config.max_retries - 1:
                    raise Exception(
                        f"Failed to generate chunk after {self.config.max_retries} attempts: {str(e)}"
                    )

        raise Exception("Failed to generate chunk after all retries")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


class ReasoningAnalyzer:
    """
    Analyzes reasoning traces to determine when Markovian Thinking is appropriate.
    """

    @staticmethod
    def should_use_markovian_thinking(prompt: str) -> bool:
        """
        Determine if a prompt should use Markovian thinking based on complexity indicators.

        Args:
            prompt: The input prompt to analyze

        Returns:
            True if Markovian thinking should be used, False otherwise
        """
        # Check for complexity indicators in the prompt
        complexity_indicators = [
            "analyze",
            "evaluate",
            "compare",
            "contrast",
            "examine",
            "investigate",
            "research",
            "deep",
            "thorough",
            "comprehensive",
            "strategy",
            "plan",
            "solution",
            "approach",
            "methodology",
            "explain in detail",
            "step by step",
            "break down",
            "elaborate",
            "reason through",
            "think through",
            "consider",
            "assess",
            "solve",
            "derive",
            "calculate",
            "prove",
            "demonstrate",
            "why",
            "how",
            "what is the process",
            "outline",
            "describe in depth",
        ]

        prompt_lower = prompt.lower()
        for indicator in complexity_indicators:
            if indicator in prompt_lower:
                logger.info(
                    f"Using Markovian thinking for prompt containing '{indicator}'"
                )
                return True

        # If the prompt is very long, it might benefit from chunked processing
        if len(prompt) > 500:  # Arbitrary threshold for longer prompts
            logger.info("Using Markovian thinking for long prompt")
            return True

        return False
