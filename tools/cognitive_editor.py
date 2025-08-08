# /tools/cognitive_editor.py

import ollama
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# A small, fast model dedicated to summarization.
COMPRESSION_MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_0"# Or another small, efficient model.

class WorkingMemoryManager:
    """
    Manages the agent's short-term scratchpad, including truncation and summarization.
    """
    def __init__(self, max_tokens: int = 4096, compression_chunk_size: int = 1024):
        self.max_tokens = max_tokens
        self.compression_chunk_size = compression_chunk_size
        self.raw_scratchpad = ""
        self.compressed_chunks = []
        self.new_content_buffer = ""

    def add_entry(self, thought: str, action: str, observation: str):
        """Adds a new turn to the scratchpad and triggers compression if needed."""
        entry = f"Thought: {thought}\nAction: {action}\nObservation: {observation}\n---\n"
        self.raw_scratchpad += entry
        self.new_content_buffer += entry

        # Trigger compression when the buffer reaches the chunk size
        if len(self.new_content_buffer.split()) > self.compression_chunk_size:
            self._trigger_compression()

        # Enforce the hard limit on the raw scratchpad
        self._truncate_scratchpad()

    def get_context(self) -> str:
        """Returns the full working memory context for the main Reasoner."""
        compressed_summary = "\\n".join(self.compressed_chunks)
        return f"**Compressed Summary of Past Events:**\\n{compressed_summary}\\n\\n**Most Recent Events (Raw):**\\n{self.raw_scratchpad}"

    def _trigger_compression(self):
        """Calls a small LLM to compress the new content buffer."""
        logging.info("Cognitive Editor: Compressing new content chunk...")
        try:
            prompt = f"Summarize the key insights and events from the following agent scratchpad entries into a single, concise paragraph:\\n\\n{self.new_content_buffer}"
            response = ollama.generate(model=COMPRESSION_MODEL, prompt=prompt)
            summary = response['response'].strip()
            self.compressed_chunks.append(summary)
            logging.info(f"Cognitive Editor: New compressed chunk created: '{summary}'")
            # Clear the buffer after compression
            self.new_content_buffer = ""
        except Exception as e:
            logging.error(f"Cognitive Editor: Failed to compress chunk: {e}")

    def _truncate_scratchpad(self):
        """Ensures the raw scratchpad does not exceed the max token limit."""
        tokens = self.raw_scratchpad.split()
        if len(tokens) > self.max_tokens:
            excess_tokens = len(tokens) - self.max_tokens
            # Find the position to cut the string from the beginning
            cut_off_point = 0
            tokens_to_remove = 0
            for i, token in enumerate(tokens):
                tokens_to_remove += 1
                cut_off_point += len(token) + 1 # +1 for the space
                if tokens_to_remove >= excess_tokens:
                    break
            self.raw_scratchpad = self.raw_scratchpad[cut_off_point:]
