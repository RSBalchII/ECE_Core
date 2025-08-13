import concurrent.futures
import requests
import json
import logging
import os
import re
from datetime import datetime

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
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

class ExtractionAgent:
    """
    A Tier 2 agent that scans a web page (e.g., an LLM chat) and extracts
    the raw conversation history for processing by other agents.
    """
    def __init__(self):
        self.blackboard_path = "extractor_blackboard.md"

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

    def _simulate_browser_extraction(self, page_html: str) -> list:
        """
        Simulates the extraction of content from a browser page using your JavaScript logic.
        This function uses your JS logic to process a given HTML string.
        """
        extracted_content = []
        # --- Your JavaScript logic translated to Python ---
        # NOTE: This is a simplified, direct translation. In a real implementation,
        # a more robust HTML parser like BeautifulSoup would be used.
        # This code simulates the output of your JS snippet.
        
        # Simulating the extraction from a simple HTML structure
        user_prompt_match = re.search(r'<user-query>(.*?)</user-query>', page_html, re.DOTALL)
        if user_prompt_match:
            extracted_content.append({
                "type": "User",
                "timestamp": datetime.now().isoformat(),
                "response_content": user_prompt_match.group(1).strip(),
                "thinking_content": ""
            })

        sybil_response_match = re.search(r'<model-response>(.*?)</model-response>', page_html, re.DOTALL)
        if sybil_response_match:
            thinking_match = re.search(r'<div data-test-id="thoughts-content".*?>(.*?)</div>', sybil_response_match.group(1), re.DOTALL)
            extracted_content.append({
                "type": "Sybil",
                "timestamp": datetime.now().isoformat(),
                "response_content": sybil_response_match.group(1).strip(),
                "thinking_content": thinking_match.group(1).strip() if thinking_match else ""
            })
            
        return extracted_content

    def orchestrate_extraction(self, page_html: str) -> str:
        """
        Orchestrates the process of extracting content and passing it to the archivist.

        Args:
            page_html: The HTML content of the page to scan.

        Returns:
            A string confirming the extraction and its destination.
        """
        logging.info(f"ExtractionAgent: Scanning page for content at {datetime.now().isoformat()}")
        
        # 1. Simulate the extraction of content
        extracted_content = self._simulate_browser_extraction(page_html)
        
        # 2. Log the process to the blackboard
        json_output = json.dumps(extracted_content, indent=2)
        new_blackboard_content = f"## Extracted Chat Log at {datetime.now().isoformat()}\n\n"
        new_blackboard_content += f"```json\n{json_output}\n```\n\n"
        self._manage_blackboard(new_blackboard_content)

        # 3. Pass the extracted data to the Archivist for processing
        # This is a conceptual placeholder for a real API call to the ArchivistAgent
        logging.info("ExtractionAgent: Passing raw data to the Archivist for processing...")
        return f"Extraction complete. {len(extracted_content)} conversation turns were extracted and sent to the Archivist."

if __name__ == "__main__":
    # --- Example Usage ---
    extraction_agent = ExtractionAgent()
    
    # A simplified, simulated HTML page from a chat session
    simulated_html = """
    <div id="chat-container">
      <user-query>What are the key components of our architecture?</user-query>
      <model-response>
        Sybil is planning...
        <div data-test-id="thoughts-content">
          Thinking about the architecture...
        </div>
      </model-response>
    </div>
    """
    
    extraction_result = extraction_agent.orchestrate_extraction(simulated_html)
    
    print("--- Extraction Agent Report ---")
    print(extraction_result)