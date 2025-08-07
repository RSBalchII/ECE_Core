"""
This module provides file I/O operations with a standardized dictionary response.
"""
import os

def read_file(filepath: str) -> dict:
    """
    Reads the entire content of a file at the given path.

    Args:
        filepath: The path to the file.

    Returns:
        A dictionary with 'status' and 'result' keys.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return {'status': 'success', 'result': content}
    except FileNotFoundError:
        return {'status': 'error', 'result': f"File not found: {filepath}"}
    except UnicodeDecodeError as e:
        return {'status': 'error', 'result': f"Decoding error: {e}. This might be a binary file."}
    except Exception as e:
        return {'status': 'error', 'result': str(e)}

def write_to_file(filepath: str, content: str) -> dict:
    """
    Writes the given content to the specified file, overwriting it if it exists.

    Args:
        filepath: The path to the file.
        content: The content to write to the file.

    Returns:
        A dictionary with 'status' and 'result' keys.
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)
        return {'status': 'success', 'result': f"Successfully wrote to {filepath}"}
    except Exception as e:
        return {'status': 'error', 'result': str(e)}

def append_to_file(filepath: str, content: str) -> dict:
    """
    Appends the given content to the specified file.

    Args:
        filepath: The path to the file.
        content: The content to append to the file.

    Returns:
        A dictionary with 'status' and 'result' keys.
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'a') as f:
            f.write(content)
        return {'status': 'success', 'result': f"Successfully appended to {filepath}"}
    except Exception as e:
        return {'status': 'error', 'result': str(e)}
