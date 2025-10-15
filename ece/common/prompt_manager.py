"""
Context-aware prompt manager for the ECE system.

This module provides functionality to manage, truncate, and optimize prompts
to prevent context overflow issues with LLMs.
"""

import tiktoken
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class PromptConfig:
    """Configuration for prompt management"""
    max_tokens: int = 32768  # Default to 32k context window
    reserved_tokens: int = 1000  # Tokens to reserve for response
    model_name: str = "gpt-4"  # Default model for token counting
    strategy: str = "intelligent"  # 'intelligent', 'truncate', 'chunk', or 'summarize'


class PromptManager:
    """
    A context-aware prompt manager that handles prompt truncation and management
    to prevent context overflow issues with LLMs.
    """

    def __init__(self, config: Optional[PromptConfig] = None):
        self.config = config or PromptConfig()
        # Initialize the tokenizer based on the model name
        try:
            self.encoder = tiktoken.encoding_for_model(self.config.model_name)
        except KeyError:
            # Fallback to a common encoding if the model isn't found
            self.encoder = tiktoken.get_encoding("cl100k_base")
        self.logger = logging.getLogger(__name__)

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a given text.
        """
        return len(self.encoder.encode(text))

    def truncate_intelligently(self, text: str, max_tokens: Optional[int] = None) -> str:
        """
        Truncate text intelligently, trying to preserve semantic meaning.
        """
        max_tokens = max_tokens or (self.config.max_tokens - self.config.reserved_tokens)
        tokens = self.encoder.encode(text)
        
        if len(tokens) <= max_tokens:
            return text

        # Simple strategy: truncate from the end while preserving beginning
        # In a more sophisticated implementation, we could implement
        # more intelligent truncation (e.g., preserving important sections)
        truncated_tokens = tokens[:max_tokens]
        truncated_text = self.encoder.decode(truncated_tokens)
        
        self.logger.warning(
            f"Intelligently truncated prompt from {len(tokens)} to {len(truncated_tokens)} tokens"
        )
        return truncated_text

    def chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """
        Split text into chunks of specified token size.
        """
        tokens = self.encoder.encode(text)
        chunks = []
        
        for i in range(0, len(tokens), chunk_size):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.encoder.decode(chunk_tokens)
            chunks.append(chunk_text)
        
        self.logger.info(f"Split text into {len(chunks)} chunks of ~{chunk_size} tokens each")
        return chunks

    def summarize_text(self, text: str, target_ratio: float = 0.5) -> str:
        """
        Create a summary of text by reducing it to the target ratio.
        Note: This is a placeholder implementation. A real implementation would
        call an LLM to generate a summary.
        """
        tokens = self.encoder.encode(text)
        target_tokens = int(len(tokens) * target_ratio)
        
        if len(tokens) <= target_tokens:
            return text

        # Simple truncation as a placeholder for actual summarization
        summary_tokens = tokens[:target_tokens]
        summary_text = self.encoder.decode(summary_tokens)
        
        self.logger.info(
            f"Summarized text from {len(tokens)} to {len(summary_tokens)} tokens "
            f"(target ratio: {target_ratio})"
        )
        return summary_text

    def prepare_prompt(self, prompt: str, context: Optional[str] = None) -> str:
        """
        Prepare a prompt for sending to an LLM, ensuring it fits within context limits.
        """
        # Combine prompt and context if provided
        full_text = f"{context}\n\n{prompt}" if context else prompt
        
        # Check token count
        token_count = self.count_tokens(full_text)
        available_tokens = self.config.max_tokens - self.config.reserved_tokens
        
        if token_count <= available_tokens:
            self.logger.info(f"Prompt fits within context: {token_count}/{available_tokens} tokens")
            return full_text

        self.logger.warning(
            f"Prompt exceeds context limit: {token_count}/{available_tokens} tokens. "
            f"Applying {self.config.strategy} strategy..."
        )

        # Apply the configured strategy
        if self.config.strategy == "truncate":
            return self.truncate_intelligently(full_text, available_tokens)
        elif self.config.strategy == "chunk":
            chunks = self.chunk_text(full_text, available_tokens)
            # For now, return the first chunk - in a real implementation, 
            # you might handle multiple chunks differently
            return chunks[0] if chunks else full_text
        elif self.config.strategy == "summarize":
            return self.summarize_text(full_text, available_tokens / token_count)
        else:  # Default to intelligent truncation
            return self.truncate_intelligently(full_text, available_tokens)

    def get_context_usage_stats(self, text: str) -> Dict[str, Any]:
        """
        Get detailed statistics about context usage for a text.
        """
        token_count = self.count_tokens(text)
        available_tokens = self.config.max_tokens - self.config.reserved_tokens
        
        return {
            "token_count": token_count,
            "max_tokens": self.config.max_tokens,
            "reserved_tokens": self.config.reserved_tokens,
            "available_tokens": available_tokens,
            "usage_percentage": (token_count / available_tokens) * 100 if available_tokens > 0 else 0,
            "over_limit": token_count > available_tokens
        }