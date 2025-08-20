
import os

def load_combined_text(file_path: str) -> str:
    """
    Loads the full text content from a single file.

    Args:
        file_path (str): The path to the text file.

    Returns:
        str: The content of the file as a single string, or an empty string if not found.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return ""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"An error occurred loading {file_path}: {e}")
        return ""

if __name__ == '__main__':
    # This path will need to be adjusted to your actual file location.
    path_to_text = '../../combined_text.txt' 
    content = load_combined_text(path_to_text)
    if content:
        print(f"Successfully loaded {len(content)} characters from the combined text file.")
        print("Sample content:", content[:200])
