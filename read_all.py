import json
import os
import chardet

def create_full_corpus_recursive():
    """
    Aggregates all readable text content from a directory and its subdirectories
    into a single text corpus, correctly preserving special characters and emojis
    by auto-detecting file encodings.
    """
    # Run this script from the root of your project directory
    root_dir = '.'
    output_file = 'combined_text.txt'
    
    # Define file extensions to process
    text_extensions = ('.json', '.md', '.poml', '.yaml', '.txt', '.py', '.js', '.html', '.css', '.sh', '.ps1')
    
    # Define directories to ignore
    ignore_dirs = ['llama.cpp', '.git', '.venv', '__pycache__', 'node_modules', 'vendor', 'build', 'dist']

    files_to_process = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip ignored directories
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith('.')]
        
        for f in filenames:
            if f.endswith(text_extensions):
                files_to_process.append(os.path.join(dirpath, f))

    files_to_process.sort()
    
    if not files_to_process:
        print(f"No processable files found in '{root_dir}' or its subdirectories.")
        return
        
    print(f"Found {len(files_to_process)} text-based files to process.")
    
    # Use 'w' to create a new file, ensuring it's encoded in UTF-8
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for file_path in files_to_process:
            print(f"Processing '{file_path}'...")
            try:
                with open(file_path, 'rb') as raw_file:
                    raw_data = raw_file.read()
                
                decoded_content = None
                try:
                    # Try decoding with UTF-8 first
                    decoded_content = raw_data.decode('utf-8')
                except UnicodeDecodeError:
                    # If UTF-8 fails, use chardet to detect encoding
                    detection = chardet.detect(raw_data)
                    encoding = detection['encoding'] if detection['confidence'] > 0.5 else 'latin-1'
                    decoded_content = raw_data.decode(encoding, errors='replace')

                outfile.write(f"--- START OF FILE: {file_path} ---\n\n")
                
                # If it's a JSON file, attempt to extract 'response_content'
                if file_path.endswith('.json'):
                    try:
                        data = json.loads(decoded_content)
                        content_found = False
                        if isinstance(data, list):
                            for entry in data:
                                if isinstance(entry, dict) and 'response_content' in entry:
                                    content = entry.get('response_content', '')
                                    if content:
                                        outfile.write(content + '\n\n')
                                        content_found = True
                        if not content_found:
                            # If no 'response_content' is found, write the whole file
                            outfile.write(decoded_content + '\n\n')
                    except json.JSONDecodeError:
                        # If JSON is invalid, write the raw decoded content
                        outfile.write(decoded_content + '\n\n')
                else:
                    # For all other text files, write the entire content
                    outfile.write(decoded_content + '\n\n')

                outfile.write(f"--- END OF FILE: {file_path} ---\n\n")

            except Exception as e:
                print(f"An unexpected error occurred with file '{file_path}': {e}")
                
    print(f"\nCorpus aggregation complete. All content has been saved to '{output_file}'.")

if __name__ == '__main__':
    create_full_corpus_recursive()
