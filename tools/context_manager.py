"""
This module provides functions for managing conversational context.
"""
import json
import os

def load_context(filepath: str) -> str:
    """
    Loads conversational context from a JSON file.

    Args:
        filepath: The path to the JSON file.

    Returns:
        The JSON content as a string, or an empty string if the file doesn't exist.
    """
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.dumps(json.load(f))
    return ""

def save_context(filepath: str, conversation_history: list):
    """
    Saves the conversation history to a JSON file.

    Args:
        filepath: The path to the JSON file.
        conversation_history: A list of conversation turns.
    """
    with open(filepath, 'w') as f:
        json.dump(conversation_history, f, indent=2)

def add_turn_to_context(conversation_history: list, user_input: str, sybil_response: str) -> list:
    """
    Adds a new turn to the conversation history.

    Args:
        conversation_history: The current conversation history.
        user_input: The user's input for the current turn.
        sybil_response: Sybil's response for the current turn.

    Returns:
        The updated conversation history.
    """
    conversation_history.append({
        "user": user_input,
        "sybil": sybil_response
    })
    return conversation_history
