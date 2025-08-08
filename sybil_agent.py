# sybil_agent.py (Refactored)
# Description: Implements a tool registry for dynamic tool execution.

import logging

# Import all tool functions
from tools.file_io import list_project_files, read_multiple_files
from tools.web_search import web_search
from tools.code_analyzer import analyze_code
from tools.memory_tool import store_memory, retrieve_similar_memories
from tools.vision_tool import analyze_screen
from tools.gui_automation_tool import move_mouse, click_mouse, type_text
from crews.archivist_crew import run_archivist_crew
from tools.cognitive_editor import WorkingMemoryManager # New: Import the memory manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SybilAgent:
    """The agent responsible for managing and executing tools."""
    def __init__(self):
        # The central registry of all available tool functions
        self._TOOL_REGISTRY = {
            "list_project_files": list_project_files,
            "read_multiple_files": read_multiple_files,
            "analyze_code": analyze_code,
            "web_search": web_search,
            "store_memory": store_memory,
            "retrieve_similar_memories": retrieve_similar_memories,
            "analyze_screen": analyze_screen,
            "move_mouse": move_mouse,
            "click_mouse": click_mouse,
            "type_text": type_text,
            "run_archivist_crew": run_archivist_crew,
        }

    def execute_tool(self, tool_name: str, tool_args: dict) -> dict:
        """
        Executes a tool from the registry with the given arguments.

        Args:
            tool_name: The name of the tool to execute.
            tool_args: A dictionary of arguments for the tool.

        Returns:
            A dictionary with the result of the tool execution.
        """
        logging.info(f"Executing tool: '{tool_name}' with args: {tool_args}")
        if tool_name not in self._TOOL_REGISTRY:
            logging.error(f"Unknown tool: {tool_name}")
            return {"status": "error", "result": f"Unknown tool: {tool_name}"}

        try:
            tool_function = self._TOOL_REGISTRY[tool_name]

            # NEW: More robust argument handling
            # If the tool expects a single positional argument, pass it directly
            if 'arg' in tool_args and len(tool_args) == 1:
                result = tool_function(tool_args['arg'])
            # If there are keyword arguments, use them
            elif tool_args:
                result = tool_function(**tool_args)
            # Handle tools that take no arguments
            else:
                result = tool_function()

            return {"status": "success", "result": result}
        except Exception as e:
            logging.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return {"status": "error", "result": f"An unexpected error occurred: {str(e)}"}