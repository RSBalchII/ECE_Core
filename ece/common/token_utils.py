"""
Token counting utilities for the ECE system.

This module provides utilities for counting tokens in text, which is essential
for preventing context overflow issues.
"""

import tiktoken
from typing import Union, List


def count_tokens(text: Union[str, List[str]], model_name: str = "gpt-4") -> int:
    """
    Count the number of tokens in a text or list of texts.

    Args:
        text: A string or list of strings to count tokens for
        model_name: The name of the model to use for tokenization

    Returns:
        The total number of tokens
    """
    try:
        encoder = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Fallback to a common encoding if the model isn't found
        encoder = tiktoken.get_encoding("cl100k_base")

    if isinstance(text, str):
        text_list = [text]
    else:
        text_list = text

    total_tokens = 0
    for t in text_list:
        total_tokens += len(encoder.encode(t))

    return total_tokens


def estimate_tokens_per_word(text: str) -> float:
    """
    Estimate the average number of tokens per word in a text.

    Args:
        text: The text to analyze

    Returns:
        The average number of tokens per word
    """
    words = text.split()
    if not words:
        return 0.0

    token_count = count_tokens(text)
    return token_count / len(words)


def truncate_text_to_tokens(
    text: str, max_tokens: int, model_name: str = "gpt-4"
) -> str:
    """
    Truncate text to fit within a maximum number of tokens.

    Args:
        text: The text to truncate
        max_tokens: The maximum number of tokens allowed
        model_name: The name of the model to use for tokenization

    Returns:
        The truncated text
    """
    try:
        encoder = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Fallback to a common encoding if the model isn't found
        encoder = tiktoken.get_encoding("cl100k_base")

    tokens = encoder.encode(text)

    if len(tokens) <= max_tokens:
        return text

    truncated_tokens = tokens[:max_tokens]
    truncated_text = encoder.decode(truncated_tokens)

    return truncated_text


def split_text_by_tokens(
    text: str, tokens_per_chunk: int, model_name: str = "gpt-4"
) -> List[str]:
    """
    Split text into chunks with a maximum number of tokens each.

    Args:
        text: The text to split
        tokens_per_chunk: The maximum number of tokens per chunk
        model_name: The name of the model to use for tokenization

    Returns:
        A list of text chunks
    """
    try:
        encoder = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Fallback to a common encoding if the model isn't found
        encoder = tiktoken.get_encoding("cl100k_base")

    tokens = encoder.encode(text)
    chunks = []

    for i in range(0, len(tokens), tokens_per_chunk):
        chunk_tokens = tokens[i : i + tokens_per_chunk]
        chunk_text = encoder.decode(chunk_tokens)
        chunks.append(chunk_text)

    return chunks
