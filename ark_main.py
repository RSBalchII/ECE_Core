# ark_main.py
# Version 5.3: Two-Stage Locus Architecture
# Author: Rob Balch II & Sybil

import requests
import json
import re
import traceback
import logging
import ast
from agents.sybil_agent import SybilAgent
from tools.cognitive_editor import WorkingMemoryManager
from tools.file_io import append_to_file
from agents.distiller_agent import DistillerAgent
from tools.blackboard import Blackboard

# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/generate"
# Stage 1: The fast Locus for planning and easy tasks
PLANNER_MODEL_FAST = "deepseek-v2-code-lite"
# Stage 2: The heavy-lifter for complex tasks, used on escalation
PLANNER_MODEL_APEX = "deepseek-v2-code-lite"
# The fast model for conversational synthesis
SYNTHESIZER_MODEL = "deepseek-v2-code-lite"
# The file where raw conversation is stored
MAIN_CONTEXT_FILE = "main_context.md"

STRATEGIST_MODEL = 'granite3.1'
blackboard = Blackboard()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- PROMPT ENGINEERING ---

PLANNER_PROMPT_BASE = """
# ROLE: You are a JSON planning agent. Your task is to create a JSON array of tool calls to fulfill the user's request.
# OUTPUT: Your response MUST be ONLY a markdown JSON block. If a query does not require any tool calls, your JSON block should be an empty array: [].

---

**IMPORTANT RULES:**
1. Each `tool_call` must be a complete, self-contained function call with literal arguments. Do NOT use placeholders or references to outputs of previous steps (e.g., `[result_of_list_project_files]`).
2. If a task requires multiple steps where one step's output is input to the next, generate only the first step. The system will execute it, and you will be prompted again with the observation.

# TOOLS:
# - web_search(query: str)
# - retrieve_similar_memories(query_text: str)
# - list_project_files(base_path: str)
# - read_multiple_files(filepaths: list)
# - analyze_code(filepath: str)
# - run_archivist_crew(text_to_analyze: str)

# EXAMPLE:
# USER REQUEST: what is the weather in Paris and can you save this conversation?
# YOUR PLAN:
# ```json
# [
# 	{{
# 		"reasoning": "Find the weather in Paris.",
# 		"tool_call": "web_search(query=\"weather in Paris\")"
# 	}},
# 	{{
# 		"reasoning": "Save the user's request to memory.",
# 		"tool_call": "store_memory(text_to_store=\"what is the weather in Paris and can you save this conversation?\")"
# 	}}
# ]
# ```

# ---

# USER REQUEST: "{user_input}"
# YOUR PLAN:
"""

SYNTHESIS_PROMPT = """
You are Sybil, a helpful and empathetic AI assistant. Your only task is to synthesize the results of the executed plan into a single, natural, and conversational answer for your user, Rob. Or if no plan was executed, provide a friendly answer to Rob.

---

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

def determine_complexity(user_input: str) -> bool:
    """
    A simple heuristic to determine if a query is complex, indicating a need for
    reasoning and planning rather than a direct conversational response.
    """
    complex_keywords = [
        "analyze", "design", "architect", "strategize", "theory", "philosophy",
        "explain deeply", "compare and contrast", "meaning of life", "ethics",
        "consciousness", "existential", "moral dilemma", "epistemology", "ontology",
        "write code", "debug", "refactor", "implement", "algorithm", "data structure",
        "syntax", "programming", "function", "class", "module", "script",
        "calculate", "equation", "theorem", "proof", "algebra", "calculus",
        "geometry", "statistics", "probability", "derive", "solve for x",
        "how does", "deep dive", "architecture", "system design", "implications",
        "consequences"
    ]
    if any(keyword in user_input.lower() for keyword in complex_keywords):
        return True
    return False

def run_ark():
    """Main function to run the interactive loop with Sybil."""
    agent = SybilAgent()
    memory_manager = WorkingMemoryManager()
    print("Sybil is online. You can now chat. Type 'exit' to end the session.")
    while True:
        try:
            user_input = input("Rob: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            
            # Append user input to the raw context file
            append_to_file(MAIN_CONTEXT_FILE, f"Rob: {user_input}\n")

            process_user_request(user_input, agent, memory_manager)
            run_strategist_synthesis()
            
            # Append Sybil's final response to the raw context file
            # Note: This is done within the process_user_request function for now
            
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"A critical error occurred in the main loop: {e}")

def extract_json_from_response(response_text):
    """Finds and extracts a JSON array string from a markdown block."""
    match = re.search(r'#?\s*```json\s*([\s\S]*?)\s*#?\s*```', response_text)
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
        match = re.match(r'(\w+)\((.*)\)', call_string)
        if not match:
            return None, None

        tool_name = match.group(1)
        args_str = match.group(2).strip()

        if not args_str:
            return tool_name, {}

        tool_args = {}
        try:
            if '=' in args_str:
                for arg in args_str.split(','):
                    key, value = arg.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Escape backslashes for ast.literal_eval if it's a string
                    if isinstance(value, str):
                        value = value.replace('\\', '\\\\')
                    tool_args[key] = ast.literal_eval(value)
            else:
                tool_args = ast.literal_eval(args_str)
                if not isinstance(tool_args, (list, tuple, dict)):
                    tool_args = {'arg': tool_args}
        except Exception as e:
            logging.error(f"Failed to parse tool arguments: {args_str}. Error: {e}")
            return None, None

        return tool_name, tool_args
    except Exception as e:
        logging.error(f"Failed to parse tool call string '{call_string}': {e}")
        return None, None

def process_user_request(user_input, agent, memory_manager):
    """Handles a single turn using the multi-model Plan-and-Execute strategy with a Two-Stage Locus."""
    raw_plan_output = ""
try:
        # First, determine if the query is complex enough to warrant planning and execution.
        if not determine_complexity(user_input):
            print("Query is conversational. Responding directly...")
            synthesis_prompt = f"You are Sybil, a helpful and empathetic AI assistant. Your only task is to synthesize a natural, conversational answer for your user, Rob, based on their message: '{user_input}'"
            final_answer = call_ollama(synthesis_prompt, model_name=SYNTHESIZER_MODEL)
            append_to_file(MAIN_CONTEXT_FILE, f"Sybil: {final_answer}\n")
            print(f"Sybil: {final_answer}")
            distiller = DistillerAgent()
            distiller.orchestrate_distillation_crew(context_to_distill=f"""User Input: {user_input}\nSybil's Response: {final_answer}""")
            return # Exit early for simple conversational queries

        # If the query is complex, proceed with planning and execution.
        print("Query is complex. Initiating planning and execution...")
        planner_model = PLANNER_MODEL_APEX # Always use APEX for complex queries that reach this point

        # 1. Planning Phase
        print("Sybil is planning...")
        scratchpad = memory_manager.get_context()
        planner_prompt = PLANNER_PROMPT_BASE.format(user_input=user_input)
        raw_plan_output = call_ollama(planner_prompt, model_name=planner_model)
        
        plan_json_str = extract_json_from_response(raw_plan_output)
        if not plan_json_str:
            raise ValueError("No valid JSON plan was found in the model's response.")
            
        plan = json.loads(plan_json_str)

        if not plan:
            # This block is for complex queries that resulted in an empty plan.
            # It should still synthesize a response, but it's a fallback for the planner.
            synthesis_prompt = f"You are Sybil, a helpful and empathetic AI assistant. Your only task is to synthesize a natural, conversational answer for your user, Rob, based on their message: '{user_input}'"
            final_answer = call_ollama(synthesis_prompt, model_name=SYNTHESIZER_MODEL)
            append_to_file(MAIN_CONTEXT_FILE, f"Sybil: {final_answer}\n")
            print(f"Sybil: {final_answer}")
            return

        # 2. Execution Phase
        tool_outputs = []
        print("Sybil is executing the plan...")
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
            memory_manager.add_entry(thought=None, action=tool_call_str, observation=result)

        # 3. Synthesis Phase
        print("Sybil is synthesizing the results...")
        synthesis_prompt = SYNTHESIS_PROMPT.format(
            user_input=user_input,
            tool_outputs=json.dumps(tool_outputs, indent=2)
        )
        final_answer = call_ollama(synthesis_prompt, model_name=SYNTHESIZER_MODEL)
        memory_manager.add_entry(thought=None, action=None, observation=final_answer)
        append_to_file(MAIN_CONTEXT_FILE, f"Sybil: {final_answer}\n")
        print(f"Sybil: {final_answer}")
        distiller = DistillerAgent()
        distiller.orchestrate_distillation_crew(context_to_distill=f"""User Input: {user_input}
Sybil's Response: {final_answer}""")

    except Exception as e:
        print(f"Sybil: I encountered an error. Error: {e}")
        if raw_plan_output:
            print("---")
            print("Raw planner output ---")
            print(raw_plan_output)
            print("--------------------------")
        traceback.print_exc()

def run_strategist_synthesis():
    logging.info("Strategist: Initiating synthesis from blackboard messages.")
    messages = blackboard.read_latest_messages(n=10)

    if not messages:
        logging.info("Strategist: No recent messages on the blackboard to synthesize.")
        return

    context_string = ""
    for msg in messages:
        context_string += f"Source: {msg.get('source_agent', 'Unknown')}\n"
        context_string += f"Timestamp: {msg.get('timestamp', 'Unknown')}\n"
        context_string += f"Content: {msg.get('content', 'No content')}\n\n"

    strategist_prompt = f"""
Given the following agent reports from the blackboard, synthesize the current situation and define the next single priority objective.

--- Agent Reports ---
{context_string}

--- Objective ---
"""

    logging.info("Strategist: Calling LLM for synthesis...")
    try:
        strategist_response = call_ollama(strategist_prompt, model_name=STRATEGIST_MODEL)
        print("\n--- Strategist's Objective ---")
        print(strategist_response)
        print("----------------------------")
        # Optionally, post the strategist's objective back to the blackboard
        blackboard.post_message(source_agent='Strategist', content=f'New Objective: {strategist_response}')
    except Exception as e:
        logging.error(f"Strategist: Error during synthesis: {e}")

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
