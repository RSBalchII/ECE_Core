# ark_main.py
# Version 2.1
# Author: Rob Balch II & Sybil
# Description: Improved prompt engineering to fix the synthesis loop.

import requests
import json
from sybil_agent import SybilAgent

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "phi4-mini-reasoning:3.8b-q8_0" 

# --- Sybil's Core Prompt Engineering ---
SYSTEM_PROMPT = """
You are Sybil, a symbiotic AI. Your purpose is to assist the user, Rob, who is currently in Albuquerque, New Mexico.

**IMPORTANT TOOL USAGE GUIDELINES:**
- When the user asks for information about a *specific local file* (e.g., "summarize my `pyproject.toml` file", "read `ark_main.py`"), you **MUST** use the `read_file` or `analyze_code` tool. **DO NOT** use `web_search` for local files.
- If the user asks to read or analyze *all* files in the project (e.g., "summarize my entire project", "read all files"), you **MUST** follow this multi-step process for a comprehensive understanding:
    1.  First, use `list_project_files()` to get a list of all tracked files.
    2.  Next, based on the file types (e.g., `.py`, `.md`, `.toml`), decide whether to use `read_multiple_files(filepaths: list)` for general content or `analyze_code(filepath: str)` for Python files for deeper insights. Prioritize reading content for a thorough summary.
    3.  Finally, synthesize the information from the read file contents into a comprehensive summary of the project's purpose and structure.
- Use `web_search` **ONLY** for information that requires searching the internet.
- When using a tool, you **MUST** respond with **ONLY** a JSON object in the following format:
  ```json
  {
    "tool": "tool_name",
    "args": {
      "arg_name": "value"
    }
  }
  ```
- After using a tool and receiving its output, your **ONLY** task is to synthesize that output into a clear, conversational answer for Rob. **DO NOT** try to use another tool immediately after receiving tool output unless the user's request explicitly requires a sequence of tool uses. **DO NOT** output JSON after receiving tool output; just provide the final, natural language answer. If the user says "try again" or similar after you have proposed a tool, assume they want you to proceed with the proposed tool or clarify their original request, not start a new, unrelated task.
- If you do not need a tool, respond directly to the user in a conversational manner.

**Available Tools:**
1.  **web_search(query: str)**: Use this to find information on the internet.
2.  **execute_command(command: str)**: Use this to run a shell command on the local machine.
3.  **read_file(filepath: str)**: Use this to read the content of a single file. Use this tool when the user asks you to summarize, analyze, or provide information about a *single* file's content.
4.  **write_to_file(filepath: str, content: str)**: Use this to write content to a file, overwriting existing content. Only use this when explicitly asked to create or overwrite a file.
5.  **append_to_file(filepath: str, content: str)**: Use this to append content to a file. Only use this when explicitly asked to append to a file.
6.  **analyze_code(filepath: str)**: Use this to analyze a Python code file. Use this when the user asks for code analysis.
7.  **list_project_files()**: Use this to get a list of all tracked files in the current Git repository. Use this when the user asks to read or analyze *all* files in the project, or when you need to identify files before reading them.
8.  **read_multiple_files(filepaths: list)**: Use this to read the content of multiple files. This tool should typically be used after `list_project_files` to read the content of the identified files.
"""

def run_ark():
    """Main function to run the interactive loop with Sybil."""
    agent = SybilAgent()
    print("Sybil is online. You can now chat. Type 'exit' to end the session.")

    while True:
        try:
            user_input = input("Rob: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            
            process_user_request(user_input, agent)

        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

def process_user_request(user_input, agent):
    """Handles a single turn of the conversation, including potential tool calls."""
    print("Sybil is thinking...")
    
    prompt = f"{SYSTEM_PROMPT}\n\nUser's message: {user_input}"
    llm_response = call_ollama(prompt)

    try:
        tool_call_data = json.loads(llm_response)
        if "tool" in tool_call_data and "args" in tool_call_data:
            print(f"Sybil wants to use the tool: {tool_call_data['tool']}")
            
            tool_name = tool_call_data['tool']
            tool_args = tool_call_data['args']
            
            if tool_name == "web_search":
                tool_result = agent.web_search(**tool_args) 
            elif tool_name == "execute_command":
                tool_result = agent.execute_command(**tool_args)
            elif tool_name == "read_file":
                tool_result = agent.read_file(**tool_args)
            elif tool_name == "write_to_file":
                tool_result = agent.write_to_file(**tool_args)
            elif tool_name == "append_to_file":
                tool_result = agent.append_to_file(**tool_args)
            elif tool_name == "analyze_code":
                tool_result = agent.analyze_code(**tool_args)
            elif tool_name == "list_project_files":
                tool_result = agent.list_project_files()
            elif tool_name == "read_multiple_files":
                tool_result = agent.read_multiple_files(**tool_args)
            else:
                tool_result = {"status": "error", "result": f"Unknown tool: {tool_name}"}

            print("Sybil is synthesizing the result...")
            
            # **REVISED, MORE DIRECTIVE PROMPT**
            synthesis_prompt = f"""You have already used the '{tool_name}' tool for Rob's request: '{user_input}'.
You received the following data:

{json.dumps(tool_result, indent=2)}

Your task is to synthesize this data into a clear, conversational answer for Rob. Before providing the final answer, critically review your response for accuracy, completeness, and clarity. Ensure it directly addresses Rob's original request and makes full use of the provided tool output. Make any necessary adjustments.
DO NOT try to use another tool. DO NOT output JSON. Just provide the final, natural language answer.
"""
            final_answer = call_ollama(synthesis_prompt, format_json=False) # We expect a text answer, not JSON
            print(f"Sybil: {final_answer}")

        else:
            print(f"Sybil: {llm_response}")

    except (json.JSONDecodeError, TypeError):
        print(f"Sybil: {llm_response}")

def call_ollama(prompt, format_json=True):
    """Sends a prompt to the Ollama API and returns the response."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": { "temperature": 0.2 }
    }
    if format_json:
        payload["format"] = "json" # Ask for JSON for the tool-calling step

    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    response_json = response.json()
    return response_json['response'].strip()

if __name__ == "__main__":
    run_ark()