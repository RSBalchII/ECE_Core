import concurrent.futures
import requests
import json

# Constants
OLLAMA_URL = "http://localhost:11434/api/generate"
TIER_3_MODEL = "deepseek-v2-code-lite"

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
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()

        # The response from Ollama is a stream of JSON objects, even with stream=False.
        # We need to parse them and concatenate the 'response' field.
        full_response = ""
        for line in response.iter_lines():
            if line:
                try:
                    json_line = json.loads(line)
                    if 'response' in json_line:
                        full_response += json_line['response']
                except json.JSONDecodeError:
                    # Ignore lines that are not valid JSON
                    pass

        return full_response.strip()

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
        self.worker_crew = []

    def _synthesize_results(self, raw_results: list) -> str:
        """
        Synthesizes raw results from worker agents into a cohesive summary.

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

        # 3. Append raw results to the blackboard file
        try:
            with open(self.blackboard_path, "a") as f:
                f.write(f"## Task: {user_request}\n\n")
                for i, result in enumerate(raw_results):
                    f.write(f"### Raw Result from Worker {i+1}\n")
                    f.write(f"{result}\n\n")
        except IOError as e:
            print(f"Error writing to blackboard file: {e}")


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
