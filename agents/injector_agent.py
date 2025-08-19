import argparse
import json
import os
import shutil
import sys
from datetime import datetime

# Add the project root to the sys.path to allow for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from chimaera.injector.parsers import parse_conversation_log

# --- Constants ---
QUARANTINE_DIR = "_quarantine"
ERROR_LOG_FILE = "injector_errors.log"
PLAINTEXT_MEMORY_FILE = "plaintext_memory.json"

def quarantine_file(original_path: str, error_message: str):
    """Moves a problematic file to the quarantine directory and logs the error."""
    file_name = os.path.basename(original_path)
    quarantine_path = os.path.join(QUARANTINE_DIR, file_name)
    try:
        shutil.move(original_path, quarantine_path)
        log_error(original_path, error_message, f"File moved to {quarantine_path}")
    except Exception as e:
        log_error(original_path, error_message, f"CRITICAL: Failed to move file to quarantine: {e}")

def log_error(file_path: str, error_message: str, additional_info: str = ""):
    """Writes a detailed error message to the error log file."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] ERROR for '{file_path}': {error_message}. {additional_info}n")

def main():
    """Main function to run the injector agent."""
    parser = argparse.ArgumentParser(
        description="Process one or more source files and ingest them into Plaintext Memory."
    )
    parser.add_argument("file_paths", nargs="+", help="One or more paths to source files.")
    args = parser.parse_args()

    successful_entries = []
    quarantined_files_count = 0
    processed_files_count = 0

    os.makedirs(QUARANTINE_DIR, exist_ok=True)

    for file_path in args.file_paths:
        if not os.path.exists(file_path):
            log_error(file_path, "File not found.")
            quarantined_files_count += 1
            continue

        try:
            # For now, we only have one parser. This is where we would add logic
            # to determine which parser to use based on file type.
            parsed_data = parse_conversation_log(file_path)

            if parsed_data:
                successful_entries.extend(parsed_data)
                processed_files_count += 1
            else:
                # The parser returns an empty list on error, so we quarantine.
                raise ValueError("Parser returned no data. File may be empty, malformed, or of the wrong format.")

        except Exception as e:
            quarantined_files_count += 1
            quarantine_file(file_path, str(e))

    # Write all successful memory entries to the final memory file
    if successful_entries:
        with open(PLAINTEXT_MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(successful_entries, f, indent=2)

    # Final report
    print("\n--- Ingestion Report ---")
    print(f"Successfully processed and ingested: {processed_files_count} file(s)")
    print(f"Quarantined due to errors: {quarantined_files_count} file(s)")
    print(f"Total memory entries created: {len(successful_entries)}")
    print(f"Output written to: {PLAINTEXT_MEMORY_FILE}")
    if quarantined_files_count > 0:
        print(f"Error details logged in: {ERROR_LOG_FILE}")
    print("------------------------\n")

if __name__ == "__main__":
    main()
