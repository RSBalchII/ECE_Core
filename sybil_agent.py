# sybill_agent.py
# Version 2.1
# Author: Rob Balch II & Sybil
# Description: Returns raw Python dictionaries instead of JSON strings.
#              Removed test block to enforce its role as a library.

import subprocess
from ddgs import DDGS
import file_io
import code_analyzer

class SybilAgent:
    """
    The core agent class that houses the tools the LLM can utilize.
    """
    def web_search(self, query: str) -> dict:
        """
        Performs a web search using DuckDuckGo and returns a dictionary of results.
        """
        print(f"Executing DDGS search for: '{query}'...")
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
                    results.append(r)
            
            if not results:
                return {"status": "error", "result": "No search results found."}

            # Return the dictionary directly
            return {"status": "success", "result": results}

        except Exception as e:
            return {"status": "error", "result": f"An error occurred during search: {str(e)}"}

    def execute_command(self, command: str) -> dict:
        """
        Executes a shell command and returns a dictionary of the output.
        """
        print(f"Executing system command: '{command}'...")
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                check=False,
                timeout=30
            )
            
            # Return the dictionary directly
            return {
                "status": "success" if result.returncode == 0 else "error",
                "return_code": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()
            }

        except Exception as e:
            return {"status": "error", "result": f"An unexpected error occurred: {str(e)}"}

    def read_file(self, filepath: str) -> dict:
        """
        Reads the content of a file.
        """
        print(f"Reading file: '{filepath}'...")
        return file_io.read_file(filepath)

    def write_to_file(self, filepath: str, content: str) -> dict:
        """
        Writes content to a file, overwriting existing content.
        """
        print(f"Writing to file: '{filepath}'...")
        return file_io.write_to_file(filepath, content)

    def append_to_file(self, filepath: str, content: str) -> dict:
        """
        Appends content to a file.
        """
        print(f"Appending to file: '{filepath}'...")
        return file_io.append_to_file(filepath, content)

    def analyze_code(self, filepath: str) -> dict:
        """
        Analyzes a Python code file.
        """
        print(f"Analyzing code in file: '{filepath}'...")
        return code_analyzer.analyze_code(filepath)

    def list_project_files(self) -> dict:
        """
        Lists all tracked files in the current Git repository.
        """
        print("Listing project files...")
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            files = result.stdout.strip().split('\n')
            return {"status": "success", "result": files}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "result": f"Git command failed: {e.stderr.strip()}"}
        except Exception as e:
            return {"status": "error", "result": f"An error occurred while listing files: {str(e)}"}

    def read_multiple_files(self, filepaths: list) -> dict:
        """
        Reads the content of multiple files and concatenates them.
        """
        print(f"Reading multiple files: {filepaths}...")
        all_content = []
        errors = []
        for filepath in filepaths:
            read_result = file_io.read_file(filepath)
            if read_result["status"] == "success":
                all_content.append(f"--- Content of {filepath} ---\n{read_result['result']}\n")
            else:
                errors.append(f"Failed to read {filepath}: {read_result['result']}")
        
        if errors:
            return {"status": "partial_success", "result": "\n".join(all_content), "errors": errors}
        else:
            return {"status": "success", "result": "\n".join(all_content)}