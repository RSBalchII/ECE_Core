import concurrent.futures
import requests
import json
import logging
import os
from datetime import datetime

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
INJECTOR_MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_0"
TIER_3_MODEL = "deepseek-v2-code-lite"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_worker_agent(task_prompt: str) -> str:
    """
    Sends a task prompt to the TIER_3_MODEL via the Ollama API.

    Args:
        task_prompt: The prompt to send to the model.

    Returns:
        The model's response as a string.
    """
    try:
        payload = {
            "model": TIER_3_MODEL,
            "prompt": task_prompt,
            "stream": False
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        response.raise_for_status()

        response_json = response.json()
        if 'response' in response_json:
            return response_json['response'].strip()
        else:
            return "Error: No 'response' field found in Ollama output."

    except requests.exceptions.RequestException as e:
        return f"Error communicating with Ollama: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

class InjectionAgent:
    """
    A Tier 2 agent that intercepts and enriches user prompts with context
    from the vector database before they are sent to another LLM.
    """
    def __init__(self):
        self.blackboard_path = "injector_blackboard.md"

    def _manage_blackboard(self, new_content: str):
        """
        Appends new content to the blackboard and truncates it to a maximum size.
        """
        max_size = 5000
        
        if os.path.exists(self.blackboard_path):
            with open(self.blackboard_path, "r") as f:
                existing_content = f.read()
        else:
            existing_content = ""

        combined_content = existing_content + new_content

        if len(combined_content) > max_size:
            truncated_content = combined_content[-max_size:]
        else:
            truncated_content = combined_content
        
        with open(self.blackboard_path, "w") as f:
            f.write(truncated_content)

    def _get_context_from_archivist(self, user_prompt: str) -> str:
        """
        Simulates querying the ArchivistAgent for relevant context.
        In a real implementation, this would be a direct API call to the Archivist.
        """
        logging.info("InjectionAgent: Querying Archivist for context...")
        # Placeholder simulation of Archivist's response
        return "Context: The user is building a hierarchical agentic architecture. Key models are deepseek-r1 for workers and deepseek-coder-v2 for the main brain."

    def _inject_context(self, original_prompt: str, context: str) -> str:
        """
        Uses the INJECTOR_MODEL to combine the original prompt with context.
        """
        prompt = f"""
        # ROLE: You are an AI Injection Agent.
        # TASK: Revise the user's original prompt by injecting the provided context.
        # INSTRUCTIONS:
        # 1. Integrate the context naturally into the original prompt.
        # 2. The output should be a single, coherent prompt.
        
        # --- ORIGINAL PROMPT ---
        # "{original_prompt}"
        
        # --- CONTEXT ---
        # "{context}"
        
        # --- REVISED PROMPT ---
        """
        try:
            payload = {
                "model": INJECTOR_MODEL,
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(OLLAMA_URL, json=payload, timeout=300)
            response.raise_for_status()
            response_json = response.json()
            return response_json['response'].strip()
        except Exception as e:
            logging.error(f"Error during context injection: {e}")
            return original_prompt # Fallback to original prompt on error

    def orchestrate_injection(self, user_prompt: str) -> str:
        """
        Orchestrates the process of intercepting, enriching, and revising a user prompt.

        Args:
            user_prompt: The raw prompt from the user.

        Returns:
            The final, context-enriched prompt.
        """
        logging.info(f"InjectionAgent: Intercepting user prompt at {datetime.now().isoformat()}")
        
        # 1. Get relevant context from the Archivist
        context = self._get_context_from_archivist(user_prompt)

        # 2. Inject the context into the original prompt
        revised_prompt = self._inject_context(user_prompt, context)
        
        # 3. Log the process to the blackboard
        new_blackboard_content = f"## Intercepted Prompt at {datetime.now().isoformat()}\n"
        new_blackboard_content += f"**Original Prompt:** {user_prompt}\n"
        new_blackboard_content += f"**Injected Context:** {context}\n"
        new_blackboard_content += f"**Revised Prompt:** {revised_prompt}\n\n"
        self._manage_blackboard(new_blackboard_content)

        return revised_prompt

if __name__ == "__main__":
    # --- Example Usage ---
    injection_agent = InjectionAgent()
    raw_prompt = "What are the core components of our architecture?"
    
    final_injected_prompt = injection_agent.orchestrate_injection(raw_prompt)
    
    print("--- Final Injected Prompt ---")
    print(final_injected_prompt)