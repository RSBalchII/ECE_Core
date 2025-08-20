import json
import logging
from chimaera.injector.memory_creator import create_memory_entry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_conversation_log(file_path: str) -> list:
    """
    Parses a conversation log JSON file and converts its entries into memory entry dictionaries.
    """
    memory_entries = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            log_data = json.load(f)

        if not isinstance(log_data, list):
            logging.warning(f"Conversation log file '{file_path}' does not contain a list of entries. Returning empty list.")
            return []

        for entry in log_data:
            content = entry.get('response_content')
            timestamp = entry.get('timestamp')
            entry_type = entry.get('type') # "Coda" or "User"

            if content and timestamp and entry_type:
                author = "User" if entry_type.lower() == "user" else "Coda"
                
                memory_entry = create_memory_entry(
                    content=content,
                    source_type="CONVERSATION_LOG",
                    source_identifier=file_path,
                    original_timestamp_utc=timestamp
                )
                # Post-creation modification to add author
                memory_entry['metadata']['author'] = author
                memory_entries.append(memory_entry)
            else:
                logging.warning(f"Skipping malformed entry in '{file_path}': {entry}")

    except FileNotFoundError:
        logging.warning(f"Conversation log file not found: {file_path}. Returning empty list.")
        return []
    except json.JSONDecodeError:
        logging.warning(f"Error decoding JSON from file: {file_path}. Returning empty list.")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred while parsing '{file_path}': {e}")
        return []

    return memory_entries