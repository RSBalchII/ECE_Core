# agents/archivist_agent.py


import concurrent.futures
import requests
import json
import logging
import os
import random # Used for simulation
import graphr1
import uuid
from tools.file_io import read_last_n_chars
from tools.blackboard import Blackboard

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

class ArchivistAgent:
    """
    A Tier 2 agent that orchestrates a crew of Tier 3 worker agents
    specialized in managing the integrity and timeline of the vector database.
    """
    def __init__(self):
        self.blackboard_path = "archivist_blackboard.md"
        # Initialize ChromaDB client
        self.graph_client = graphr1.Client()
        self.blackboard = Blackboard()
        # self.memory_archive = self.chroma_client.get_or_create_collection(name="memory_archive") # TODO: Replace with GraphR1 equivalent

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

    def orchestrate_context_management(self, context_chunk: str) -> str:
        """
        Orchestrates the worker crew to manage a new context chunk.
        This includes redundancy filtering and context appending.

        Args:
            context_chunk: The new piece of information to be managed.

        Returns:
            A final decision on how the context was handled.
        """
        # 1. Generate 5 prompt variations for analysis
        task_prompts = [
            f"Given the following new context, identify if it is highly similar to existing memories. Context: {context_chunk}",
            f"Extract all unique information and key facts from this new context. Context: {context_chunk}",
            f"Compare this context with existing memories and suggest where it might be appended. Context: {context_chunk}",
            f"Evaluate if this new context represents a change in state or a new fact. Context: {context_chunk}",
            f"If this is new information, suggest a concise entry for the vector database. Context: {context_chunk}"
        ]

        # 2. Launch the worker agents in parallel
        raw_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_prompt = {executor.submit(run_worker_agent, prompt): prompt for prompt in task_prompts}
            for future in concurrent.futures.as_completed(future_to_prompt):
                try:
                    result = future.result()
                    raw_results.append(result)
                except Exception as exc:
                    raw_results.append(f"An exception occurred: {exc}")

        # 3. Append raw results to the blackboard
        new_blackboard_content = f"## Context Management: {context_chunk[:50]}...\n\n"
        for i, result in enumerate(raw_results):
            new_blackboard_content += f"### Worker {i+1} Analysis\n"
            new_blackboard_content += f"{result}\n\n"
        self._manage_blackboard(new_blackboard_content)

        # 4. Synthesize a final decision
        # --- This is a boilerplate simulation of the final decision logic ---
        # A real implementation would use a model to make a decision based on the raw_results
        # For this example, we'll simulate a decision based on a random chance
        if random.random() > 0.5:
            decision = f"Decision: The new context was deemed sufficiently unique and was added to the database as a new entry. It contained information that was not present in previous memories."
        else:
            decision = f"Decision: The new context was highly similar to an existing entry. The new information was appended to the older context to maintain the timeline and avoid redundancy."

        return decision

    def archive_memory_chunk(self, text_chunk: str):
        """
        Archives a text chunk into the ChromaDB collection.

        Args:
            text_chunk: The piece of text to be archived.
        """
        try:
            doc_id = str(uuid.uuid4())
            self.graph_client.nodes.create(id=doc_id, label='ConceptNode', properties={'text': text_chunk, 'source': 'archivist_agent'})
            print(f"Archived chunk of {len(text_chunk)} characters.")
            self.blackboard.post_message(source_agent='ArchivistAgent', content=f'Archived chunk of {len(text_chunk)} characters.')
        except Exception as e:
            print(f"Error archiving memory chunk: {e}")

    def archive_from_working_memory(self, working_memory_path: str, chars_to_archive: int):
        """
        Reads the last n characters from the working memory file and archives them.
        """
        print(f"Archiving last {chars_to_archive} characters from {working_memory_path}...")
        
        # Read the last n characters from the working memory file
        content_to_archive = read_last_n_chars(working_memory_path, chars_to_archive)
        
        if content_to_archive:
            # Archive the content using the existing method
            self.archive_memory_chunk(content_to_archive)
            print("Successfully archived content from working memory.")
        else:
            print("Working memory file is empty or could not be read. Nothing to archive.")

    def query_memory_archive(self, query_text: str, top_k: int = 5) -> list:
        """
        Performs a semantic search on 'ConceptNode' nodes in GraphR1.

        Args:
            query_text: The text to query for.
            top_k: The maximum number of results to return.

        Returns:
            A list of dictionaries, where each dictionary contains the properties of a matching node.
        """
        try:
            results = self.graph_client.nodes.search(label='ConceptNode', query=query_text, top_k=top_k)
            return [node.properties for node in results]
        except Exception as e:
            print(f"Error querying memory archive: {e}")
            return []

if __name__ == "__main__":
    # --- Example Usage ---
    archivist = ArchivistAgent()

    # Example 1: New, unique context
    print("--- Running Context Management on New Context ---")
    new_context = "The primary purpose of the Chimaera is to act as an externalized executive function. The project is currently focused on building a hierarchical agentic architecture."
    decision_1 = archivist.orchestrate_context_management(new_context)
    print("Final Decision:")
    print(decision_1)

    print("\n" + "="*50 + "\n")

    # Example 2: Context that is a revision of an old fact
    print("--- Running Context Management on Revised Context ---")
    revised_context = "The primary purpose of the Chimaera is to act as a symbiotic AI partner. The project has recently adopted a new model for its parallel workers: deepseek-r1."
    decision_2 = archivist.orchestrate_context_management(revised_context)
    print("Final Decision:")
    print(decision_2)

    print("\n" + "="*50 + "\n")

    # --- Test Archiving ---
    print("--- Testing Memory Archival ---")
    # sample_chunk = "This is a test memory chunk to be archived in ChromaDB." # TODO: Remove or replace with GraphR1 test
    # archivist.archive_memory_chunk(sample_chunk) # TODO: Remove or replace with GraphR1 test
    # Verify the chunk was added (optional, requires querying)
    # count = archivist.memory_archive.count()
    # print(f"Current number of items in archive: {count}")