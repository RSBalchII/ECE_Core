"""
TOON (Token-Oriented Object Notation) Formatter.
A lightweight, indentation-based format designed to save tokens in LLM prompts.
"""
from typing import Any, Dict, List

def format_as_toon(data: Any, indent: int = 0) -> str:
    """
    Format data as TOON (Token-Oriented Object Notation).
    
    Rules:
    - No quotes around keys
    - No braces or commas
    - Indentation defines hierarchy (2 spaces)
    - Lists are denoted by `-`
    - Strings are unquoted unless they contain special chars (simple heuristic)
    """
    spaces = "  " * indent
    
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{spaces}{key}:")
                lines.append(format_as_toon(value, indent + 1))
            else:
                lines.append(f"{spaces}{key}: {value}")
        return "\n".join(lines)
    
    elif isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                # For complex items, start with dash then indent content
                # But TOON usually prefers:
                # - key: value
                #   other: value
                formatted_item = format_as_toon(item, indent + 1)
                # Strip first indent to align with dash
                lines.append(f"{spaces}- {formatted_item.lstrip()}")
            else:
                lines.append(f"{spaces}- {item}")
        return "\n".join(lines)
    
    else:
        return str(data)
