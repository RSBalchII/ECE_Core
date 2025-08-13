import concurrent.futures
import requests
import json
import logging
import os
from datetime import datetime
from tools.file_io import read_last_n_chars, write_and_truncate
from tools.blackboard import Blackboard

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
TIER_3_MODEL = "deepseek-v2-code-lite"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_distiller_worker(task_prompt: str) -> str:
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

class DistillerAgent:
    """
    An agent that orchestrates a crew of Tier3Worker agents to distill context
    and route it to appropriate memory files.
    """
    def __init__(self):
        self.blackboard_path = "distiller_blackboard.md"
        self.life_history_path = "life-history.md"
        self.memories_path = "memories.md"
        self.thinking_processes_path = "thinking_processes.md"
        self.blackboard = Blackboard()

    

    def orchestrate_distillation_crew(self, context_to_distill: str):
        """
        Orchestrates a crew of Tier3Worker agents to distill the given context
        and writes the raw results to the distiller blackboard.

        Args:
            context_to_distill: The string context to be distilled.
        """
        T3_PROMPTS = [
            f"Analyze the following text for objective facts and significant life events. Extract key factual information suitable for a life history document. Text: {context_to_distill}",
            f"Review the following text for relational milestones, emotional experiences, and significant personal interactions. Summarize these aspects for a personal memories document. Text: {context_to_distill}",
            f"Examine the following text for metacognitive insights, thought processes, problem-solving approaches, and learning experiences. Condense these into entries for a thinking processes document. Text: {context_to_distill}"
        ]

        raw_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(T3_PROMPTS)) as executor:
            future_to_prompt = {executor.submit(run_distiller_worker, prompt): prompt for prompt in T3_PROMPTS}
            for future in concurrent.futures.as_completed(future_to_prompt):
                try:
                    result = future.result()
                    raw_results.append(result)
                except Exception as exc:
                    raw_results.append(f"An exception occurred: {exc}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_blackboard_content = f"## Distillation at {timestamp}\n\n"
        new_blackboard_content += f"Original Context:\n```\n{context_to_distill}\n```\n\n"
        for i, result in enumerate(raw_results):
            new_blackboard_content += f"### Tier3Worker Result {i+1}\n"
            new_blackboard_content += f"{result}\n\n"
        
        self.blackboard.post_message(source_agent='DistillerAgent', content=new_blackboard_content)

    def route_and_archive(self):
        """
        Reads the distiller blackboard, routes the distilled information to the
        appropriate core memory files (life-history.md, memories.md, thinking_processes.md),
        and appends the content.
        """
        if not os.path.exists(self.blackboard_path):
            print(f"Distiller blackboard not found at {self.blackboard_path}. Nothing to route.")
            return

        with open(self.blackboard_path, "r") as f:
            blackboard_content = f.read()

        # Simple routing logic based on keywords. This can be made more sophisticated.
        # For now, we'll just append the entire blackboard content to all files
        # that match a keyword. A more advanced implementation would parse the
        # individual worker results and route them specifically.

        # For demonstration, let's assume each worker's output is distinct enough
        # to be routed. In a real scenario, you'd parse the 'Tier3Worker Result X'
        # sections and route them individually.

        # For now, I'll just append the entire blackboard content to all files
        # that match a keyword. This is a placeholder for more sophisticated routing.
        # The prompt asks to use the content to decide which of the three core memory files
        # to append the information to. I will implement a basic keyword-based routing
        # for the *entire* blackboard content for now, as parsing individual worker
        # results would require more complex NLP which is beyond the scope of this
        # refactoring task without a dedicated parsing model.

        # Let's refine this. The prompt says "uses the content to decide which of the three core memory files to append the information to."
        # This implies a decision *per piece of information*. Since the blackboard contains
        # multiple worker results, I should try to route each result.

        # A more robust approach would involve another LLM call to categorize each result,
        # but for this task, I'll use simple keyword matching on the *worker results themselves*.

        # Split the blackboard content into individual worker results
        worker_results = blackboard_content.split("### Tier3Worker Result ")[1:] # Skip the initial part

        routed_content = {
            self.life_history_path: [],
            self.memories_path: [],
            self.thinking_processes_path: []
        }

        for i, result_block in enumerate(worker_results):
            # Extract the actual result text (after the heading and before the next heading or end)
            # Find the first newline after the heading and take everything after that.
            first_newline_after_heading = result_block.find('\n')
            if first_newline_after_heading != -1:
                result_text = result_block[first_newline_after_heading:].strip()
            else:
                result_text = result_block.strip() # Fallback if no newline found

            # Simple keyword-based routing
            if "life event" in result_text.lower() or "factual information" in result_text.lower() or "objective facts" in result_text.lower():
                routed_content[self.life_history_path].append(result_text)
            if "relational milestone" in result_text.lower() or "emotional experience" in result_text.lower() or "personal interaction" in result_text.lower():
                routed_content[self.memories_path].append(result_text)
            if "metacognitive insight" in result_text.lower() or "thought process" in result_text.lower() or "learning experience" in result_text.lower():
                routed_content[self.thinking_processes_path].append(result_text)
            
        for file_path, contents in routed_content.items():
            if contents:
                with open(file_path, "a") as f:
                    for content in contents:
                        f.write(f"\n---\nDistilled Content ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):\n{content}\n")
                print(f"Appended distilled content to {file_path}")
            else:
                print(f"No relevant content to append to {file_path}")

        # Clear the blackboard after routing
        with open(self.blackboard_path, "w") as f:
            f.write("")
        print(f"Cleared distiller blackboard at {self.blackboard_path}")