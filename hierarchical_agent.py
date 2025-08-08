import concurrent.futures
import requests
import json
import logging
import os

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
TIER_3_MODEL = "deepseek-r1:1.5b-qwen-distill-q8_0"

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
        response = requests.post(OLLAMA_URL, json=payload, timeout=300) # Added timeout
        response.raise_for_status()

        # Simplified parsing for a non-streaming response
        response_json = response.json()
        if 'response' in response_json:
            return response_json['response'].strip()
        else:
            return "Error: No 'response' field found in Ollama output."

    except requests.exceptions.RequestException as e:
        return f"Error communicating with Ollama: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

class SpecialistAgent:
    """
    A Tier 2 agent that orchestrates a crew of Tier 3 worker agents.
    """
    def __init__(self):
        self.blackboard_path = "blackboard.md"

    def _synthesize_results(self, raw_results: list) -> str:
        """
        Synthesizes raw results from worker agents into a cohesive summary.
        (This is a simple boilerplate for a full synthesis model.)

        Args:
            raw_results: A list of strings, where each string is a result from a worker.

        Returns:
            A single string containing the synthesized summary.
        """
        synthesis = "## Synthesized Results\n\n"
        for i, result in enumerate(raw_results):
            synthesis += f"### Worker {i+1} Contribution\n"
            synthesis += f"{result}\n\n"
        return synthesis

    def _manage_blackboard(self, new_content: str):
        """
        Appends new content to the blackboard and truncates it to a maximum size.
        """
        max_size = 5000 # Your defined max size in characters
        
        # Read existing content
        if os.path.exists(self.blackboard_path):
            with open(self.blackboard_path, "r") as f:
                existing_content = f.read()
        else:
            existing_content = ""

        # Combine old and new content
        combined_content = existing_content + new_content

        # Truncate if necessary
        if len(combined_content) > max_size:
            truncated_content = combined_content[-max_size:]
        else:
            truncated_content = combined_content
        
        # Write back to file
        with open(self.blackboard_path, "w") as f:
            f.write(truncated_content)

    def orchestrate_task(self, user_request: str) -> str:
        """
        Orchestrates the worker crew to perform a task based on the user request.

        Args:
            user_request: The high-level task from the user.

        Returns:
            A synthesized summary of the results from the worker crew.
        """
        # 1. Generate 5 slightly different task prompt variations
        task_prompts = [
            f"{user_request} - Focus on the perspective of a hiring manager.",
            f"{user_request} - Focus on the required technical skills and programming languages.",
            f"{user_request} - Focus on salary trends and compensation packages.",
            f"{user_request} - Focus on remote work opportunities and work-life balance.",
            f"{user_request} - Focus on the impact of AI on software development roles.",
        ]

        # 2. Launch the worker agents in parallel
        raw_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_prompt = {executor.submit(run_worker_agent, prompt): prompt for prompt in task_prompts}
            for future in concurrent.futures.as_completed(future_to_prompt):
                prompt = future_to_prompt[future]
                try:
                    result = future.result()
                    raw_results.append(result)
                except Exception as exc:
                    raw_results.append(f"'{prompt}' generated an exception: {exc}")

        # 3. Append and truncate raw results in the blackboard file
        new_blackboard_content = ""
        new_blackboard_content += f"## Task: {user_request}\n\n"
        for i, result in enumerate(raw_results):
            new_blackboard_content += f"### Raw Result from Worker {i+1}\n"
            new_blackboard_content += f"{result}\n\n"
        
        self._manage_blackboard(new_blackboard_content)

        # 4. Synthesize the results
        synthesized_result = self._synthesize_results(raw_results)

        return synthesized_result

if __name__ == "__main__":
    # Instantiate the Specialist Agent
    specialist = SpecialistAgent()

    # Define the user request
    user_request = "Analyze the recent job market for software developers with AI skills."

    # Orchestrate the task and get the final result
    final_output = specialist.orchestrate_task(user_request)

    # Print the final, synthesized output
    print(final_output)

    print(f"\nRaw results were appended to '{specialist.blackboard_path}'")