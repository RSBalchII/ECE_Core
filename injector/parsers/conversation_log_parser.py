import json
import os

def parse_conversation_log(filepath: str) -> list:
    """
    Parses a conversation log from a JSON file.

    Args:
        filepath: The path to the JSON file.

    Returns:
        A list of conversation entries, or an empty list if the file doesn't exist or is empty.
    """
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                # If the file contains a single object, wrap it in a list
                return [data]
    return []