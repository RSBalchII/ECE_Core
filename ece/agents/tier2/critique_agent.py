"""
Critique Agent for the External Context Engine (ECE).

This module implements the CritiqueAgent, which evaluates solutions
using the Exploratory Problem-Solving workflow.
"""

import os
import httpx
from typing import Dict, Any
import random


class CritiqueAgent:
    """
    The CritiqueAgent evaluates solutions and provides scores with rationale.

    This agent is part of the advanced reasoning workflows in ECE v2.0, specifically
    responsible for critiquing solution proposals in the Exploratory
    Problem-Solving Loop.
    """

    def __init__(
        self, model: str, success_threshold: float = 0.8, api_base: str = None
    ):
        """Initialize the CritiqueAgent."""
        self.model = model
        self.success_threshold = success_threshold
        self.api_base = api_base
        self.system_prompt = "You are a critique agent. Your task is to evaluate a proposed solution and its execution result against an original problem. Provide a score between 0.0 and 1.0, and a detailed rationale. The score should be clearly indicated as 'SCORE: 0.X'. Also provide suggestions for improvement."

    async def critique(
        self, original_prompt: str, proposed_solution: str, execution_result: str
    ) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Original Problem: {original_prompt}\n\nProposed Solution:\n{proposed_solution}\n\nExecution Result:\n{execution_result}\n\nCritique this solution and provide a score (0.0-1.0) and rationale.",
            },
        ]

        payload = {"model": self.model, "messages": messages, "stream": False}

        if "ollama" in self.api_base:
            url = f"{self.api_base}/api/chat"
        else:
            url = f"{self.api_base}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "")
                return content
        except httpx.RequestError as e:
            error_message = f"HTTP request failed: {e.__class__.__name__} - {e}"
            print(f"Error in CritiqueAgent: {error_message}")
            return f"Error: {error_message}"
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(f"Error in CritiqueAgent: {error_message}")
            return f"Error: {error_message}"


def main():
    """Main entry point for the Critique agent."""
    print("Critique agent initialized.")


if __name__ == "__main__":
    main()
