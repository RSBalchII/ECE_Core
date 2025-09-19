"""
Explorer Agent for the External Context Engine (ECE).

This module implements the ExplorerAgent, which proposes solutions to problems
using the Exploratory Problem-Solving workflow.
"""

import os
import httpx
from typing import Dict, Any, List
import uuid


class ExplorerAgent:
    """
    The ExplorerAgent proposes solutions to problems using creative exploration techniques.
    
    This agent is part of the advanced reasoning workflows in ECE v2.0, specifically
    responsible for generating initial solution proposals in the Exploratory 
    Problem-Solving Loop.
    """

    def __init__(self, model: str):
        """Initialize the ExplorerAgent."""
        self.model = model
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.system_prompt = "You are an expert problem solver and code generator. Your task is to propose solutions, often in the form of Python code, to given problems. Think step by step and provide the code within ```python\n...\n``` blocks."

    async def explore(self, prompt: str, current_solution: str = "", iteration_history: list = None) -> str:
        if iteration_history is None:
            iteration_history = []

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]

        if current_solution:
            messages.append({"role": "assistant", "content": f"Current solution: {current_solution}"})
        
        for entry in iteration_history:
            messages.append({"role": "assistant", "content": f"Previous attempt (Iteration {entry['iteration']}):\nSolution: {entry['explorer_response']}\nCritique: {entry['critique_response']}\nExecution Result: {entry['execution_result']}"})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{self.ollama_base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get('message', {}).get('content', '')
                return content
        except httpx.RequestError as e:
            error_message = f"HTTP request failed: {e.__class__.__name__} - {e}"
            print(f"Error in ExplorerAgent: {error_message}")
            return f"Error: {error_message}"
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(f"Error in ExplorerAgent: {error_message}")
            return f"Error: {error_message}"


def main():
    """Main entry point for the Explorer agent."""
    print("Explorer agent initialized.")


if __name__ == "__main__":
    main()