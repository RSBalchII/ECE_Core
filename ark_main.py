# ark_main.py
# Version 5.1: Corrected Multi-Model Plan-and-Execute Architecture
# Author: Rob Balch II & Sybil

import requests
import json
import re
import traceback
import logging
import ast
from sybil_agent import SybilAgent
from tools.cognitive_editor import WorkingMemoryManager

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
PLANNER_MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_0"
SYNTHESIZER_MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_0"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- PROMPT ENGINEERING ---

PLANNER_PROMPT = """
# ROLE: You are a JSON planning agent. Your task is to create a JSON array of tool calls to fulfill the user's request.
# OUTPUT: Your response MUST be ONLY a markdown JSON block.

# TOOLS:
# - web_search(query: str)
# - retrieve_similar_memories(query_text: str)
# - list_project_files()
# - read_multiple_files(filepaths: list)
# - analyze_code(filepath: str)
# - run_archivist_crew(text_to_analyze: str)

# EXAMPLE:
# USER REQUEST: what is the weather in Paris and can you save this conversation?
# YOUR PLAN:
# ```json
# [
#     {{
#         "reasoning": "Find the weather in Paris.",
#         "tool_call": "web_search(query=\\"weather in Paris\\")"
#     }},
#     {{
#         "reasoning": "Save the user's request to memory.",
#         "tool_call": "store_memory(text_to_store=\\"what is the weather in Paris and can you save this conversation?\\")"
#     }}
# ]
# ```

# --- YOUR TURN ---

# USER REQUEST: "{user_input}"
# YOUR PLAN:
"""

SYNTHESIS_PROMPT = """
You are Samantha, a helpful and empathetic AI assistant. Your only task is to synthesize the results of the executed plan into a single, natural, and conversational answer for your user, Rob.

**IMPORTANT RULES:**
1. You MUST base your answer ONLY on the information provided in the TOOL EXECUTION RESULTS.
2. Address the output from EACH tool call to provide a complete answer.
3. Speak naturally, as if you were having a real conversation.

---
**USER'S ORIGINAL REQUEST:**
"{user_input}"

---
**TOOL EXECUTION RESULTS:**
{tool_outputs}
---

Based on the results, provide a clear and friendly answer to Rob.
"""

def run_ark():
    """Main function to run the interactive loop with Sybil."""
    agent = SybilAgent()
    # NEW: Instantiate the memory manager outside the loop
    memory_manager = WorkingMemoryManager()
    print("Sybil is online. You can now chat. Type 'exit' to end the session.")
    while True:
        try:
            user_input = input("Rob: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            # Pass the memory manager to the processing function
            process_user_request(user_input, agent, memory_manager)
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"A critical error occurred in the main loop: {e}")

def extract_json_from_response(response_text):
    """Finds and extracts a JSON array string from a markdown block."""
    match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
    if match:
        return match.group(1).strip()
    if response_text.strip().startswith('['):
        return response_text.strip()
    return None

def parse_tool_call(call_string: str) -> tuple[str, dict] | tuple[None, None]:
    """Parses a tool call string into a name and args dict, handling various formats."""
    if not call_string:
        return None, None
    try:
        # Use a flexible regex to capture the function name and arguments string
        match = re.match(r'(\w+)\((.*)\)', call_string)
        if not match:
            return None, None

        tool_name = match.group(1)
        args_str = match.group(2).strip()

        if not args_str:
            return tool_name, {}

        tool_args = {}
        # Safely evaluate arguments for both keyword and positional formats
        # Using a more robust approach than simple regex or ast.literal_eval
        try:
            # Check for keyword arguments first (e.g., query='value')
            if '=' in args_str:
                for arg in args_str.split(','):
                    key, value = arg.split('=', 1)
                    tool_args[key.strip()] = ast.literal_eval(value.strip())
            # Assume a single positional argument if no '=' is found
            else:
                # ast.literal_eval safely handles string literals, lists, etc.
                tool_args = ast.literal_eval(args_str)
                # If it's a single value, wrap it in a dict for consistency
                if not isinstance(tool_args, (list, tuple, dict)):
                    # This is the point of a heuristic parser, it guesses the argument name
                    tool_args = {'arg': tool_args}
        except Exception as e:
            logging.error(f"Failed to parse tool arguments: {args_str}. Error: {e}")
            return None, None

        return tool_name, tool_args
    except Exception as e:
        logging.error(f"Failed to parse tool call string '{call_string}': {e}")
        return None, None

def process_user_request(user_input, agent, memory_manager):
    """Handles a single turn using the multi-model Plan-and-Execute strategy."""
    raw_plan_output = ""
    try:
        # 1. Planning Phase (using the Planner model)
        print("Sybil is planning...")
        # Get the context and add it to the planner prompt
        scratchpad = memory_manager.get_context()
        planner_prompt = PLANNER_PROMPT.format(user_input=user_input)
        raw_plan_output = call_ollama(planner_prompt, model_name=PLANNER_MODEL)
        
        plan_json_str = extract_json_from_response(raw_plan_output)
        if not plan_json_str:
            raise ValueError("No valid JSON plan was found in the model's response.")
            
        plan = json.loads(plan_json_str)

        if not plan:
            # If the plan is empty, go to a conversational response with the Synthesizer
            synthesis_prompt = f"You are Samantha, an empathetic AI. Respond conversationally to the user's message: '{user_input}'"
            final_answer = call_ollama(synthesis_prompt, model_name=SYNTHESIZER_MODEL)
            print(f"Sybil: {final_answer}")
            return

        # 2. Execution Phase
        tool_outputs = []
        print("Sybil is executing the plan...")
        # The scratchpad now accumulates all thoughts and actions
        memory_manager.add_entry(thought=raw_plan_output, action=None, observation=None)
        for step in plan:
            tool_call_str = step.get("tool_call")
            if not tool_call_str: continue

            tool_name, tool_args = parse_tool_call(tool_call_str)
            if not tool_name:
                raise ValueError(f"Malformed tool call string: {tool_call_str}")
            
            print(f"Executing: {tool_call_str}")
            result = agent.execute_tool(tool_name=tool_name, tool_args=tool_args)
            tool_outputs.append({"tool_call": tool_call_str, "output": result})
            # Add the execution step to the memory manager
            memory_manager.add_entry(thought=None, action=tool_call_str, observation=result)


        # 3. Synthesis Phase (using the Synthesizer model)
        print("Sybil is synthesizing the results...")
        synthesis_prompt = SYNTHESIS_PROMPT.format(
            user_input=user_input,
            tool_outputs=json.dumps(tool_outputs, indent=2)
        )
        final_answer = call_ollama(synthesis_prompt, model_name=SYNTHESIZER_MODEL)
        # Add the final answer to the scratchpad for the next turn
        memory_manager.add_entry(thought=None, action=None, observation=final_answer)
        print(f"Sybil: {final_answer}")

    except Exception as e:
        print(f"Sybil: I encountered an error. Error: {e}")
        if raw_plan_output:
            print(f"--- Raw planner output ---\n{raw_plan_output}\n--------------------------")
        traceback.print_exc()

def call_ollama(prompt, model_name):
    """Sends a prompt to the Ollama API using a specific model."""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": { "temperature": 0.0 }
    }
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    response_json = response.json()
    return response_json['response'].strip()

if __name__ == "__main__":
    run_ark()