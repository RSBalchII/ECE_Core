#!/usr/bin/env python3
"""
Root Reader: Aggregates content from relevant project files for orchestration.

This script scans the project directory and combines the content of source code,
configuration, and documentation files into a single text file (combined_text.txt).

It ignores files with more than 2000 lines, and skips common combined outputs and package manifest files.

It respects the current project structure:
- Root level scripts and docs
- tools/: Sovereign Core (JS/HTML/CSS)
- specs/: System Specifications
- scripts/: CI/Utility scripts
"""
import argparse
import json
import os
from typing import List, Tuple, Any

def find_project_root(start_path: str | None = None) -> str:
    """
    Locate project root by looking for indicators like .git, package.json, README.md
    """
    if start_path is None:
        start_path = os.path.abspath(__file__)

    path = os.path.abspath(start_path)
    if os.path.isfile(path):
        path = os.path.dirname(path)

    root_indicators = (".git", "package.json", "README.md")
    while True:
        if any(os.path.exists(os.path.join(path, ind)) for ind in root_indicators):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return os.getcwd()
        path = parent

def file_has_too_many_lines(file_path: str, max_lines: int = 2000) -> bool:
    """
    Return True if file has more than max_lines lines.
    Counted efficiently by reading in binary and summing newline bytes.
    """
    try:
        with open(file_path, 'rb') as f:
            lines = 0
            for chunk in iter(lambda: f.read(8192), b''):
                lines += chunk.count(b'\n')
                if lines > max_lines:
                    return True
    except Exception:
        # If we can't read the file, be conservative and skip it
        return True
    return False


def get_allowed_files(project_root: str) -> List[Tuple[str, str]]:
    """
    Returns list of (file_path, section_name) for all relevant project files.
    """
    allowed_files = []
    
    # Extensions we care about
    code_exts = {'.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.bat', '.ps1', '.sh', '.yaml', '.yml'}
    
    # Directories to completely ignore
    ignored_dirs = {'context','.git', '.venv', 'browser_data', 'archive', '__pycache__', 'node_modules', '.github'}
    
    # Files to ignore (add common package manifests and combined outputs)
    ignored_files = {
        'package-lock.json',
        'package.json',
        'yarn.lock',
        'pnpm-lock.yaml',
        'combined_text.txt',
        'combined_text.json',
        'cozo_lib_wasm_bg.wasm',
        'combined_memory.json',
        'cozo_import_memory.json'
    }

    for root, dirs, files in os.walk(project_root):
        # Filter directories in-place to avoid walking into ignored ones
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        
        rel_root = os.path.relpath(root, project_root)
        section = "ROOT" if rel_root == "." else rel_root.replace(os.sep, "_").upper()

        for f in files:
            fname_lower = f.lower()
            # Skip explicitly ignored files and common combined outputs
            if fname_lower in ignored_files or 'combined_text' in fname_lower or 'combined_memory' in fname_lower:
                continue
            
            ext = os.path.splitext(f)[1].lower()
            if ext in code_exts:
                full_path = os.path.join(root, f)
                # Skip files that are too large (more than 2000 lines)
                if file_has_too_many_lines(full_path, 2000):
                    print(f"Skipping '{os.path.relpath(full_path, project_root)}' — exceeds 2000 lines.")
                    continue
                allowed_files.append((full_path, section))
                
    return allowed_files

def to_yaml_style(obj: Any, indent: int = 0) -> str:
    """
    Recursively converts a JSON-compatible object to a YAML-like string.
    """
    lines = []
    prefix = "  " * indent
    
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{prefix}{k}:")
                lines.append(to_yaml_style(v, indent + 1))
            else:
                # Handle multiline strings safely
                v_str = str(v)
                if '\n' in v_str:
                     lines.append(f"{prefix}{k}: |")
                     for line in v_str.split('\n'):
                         lines.append(f"{prefix}  {line}")
                else:
                    lines.append(f"{prefix}{k}: {v}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                # For list items that are objects, we want the properties to align slightly differently
                # But for simplicity in this custom dumper:
                sub = to_yaml_style(item, indent + 1)
                lines.append(sub)
            else:
                lines.append(f"{prefix}- {item}")
    else:
        return f"{prefix}{obj}"

    return "\n".join(lines)

def create_project_corpus(
    output_file: str | None = None,
    dry_run: bool = False,
):
    """
    Aggregates content from project files into a single corpus.
    """
    project_root = find_project_root()
    output_file = output_file or os.path.join(project_root, "combined_text.txt")

    print(f"Project Root Detected: {project_root}")
    allowed_files = get_allowed_files(project_root)

    if not allowed_files:
        print(f"No relevant files found in '{project_root}'.")
        return

    print(f"Found {len(allowed_files)} files to process.")

    if dry_run:
        print(f"Dry run enabled — would process {len(allowed_files)} files:")
        for file_path, section in allowed_files:
            print(f"  - {os.path.relpath(file_path, project_root)} ({section})")
        return

    memory_records = []

    with open(output_file, "w", encoding="utf-8") as outfile:
        # Add a file map at the very top for the orchestrator
        outfile.write("=== PROJECT FILE MAP ===\n")
        for file_path, section in allowed_files:
            rel_path = os.path.relpath(file_path, project_root)
            outfile.write(f"- {rel_path} ({section})\n")
        outfile.write("========================\n\n")

        for file_path, section in allowed_files:
            rel_path = os.path.relpath(file_path, project_root)
            print(f"Processing '{rel_path}'...")
            try:
                with open(file_path, "rb") as raw_file:
                    raw_data = raw_file.read()
                if not raw_data:
                    continue
                
                try:
                    decoded_content = raw_data.decode("utf-8")
                except UnicodeDecodeError:
                    decoded_content = raw_data.decode("utf-8", errors="replace")

                ext = os.path.splitext(file_path)[1].lower()
                final_content = decoded_content
                
                # Upgrade: Convert JSON to YAML-like text
                if ext == '.json':
                    try:
                        json_obj = json.loads(decoded_content)
                        # Use pretty print json as a reliable fallback or strict yaml style
                        # The user asked for "YAML-like string (key: value) or pretty-printed JSON (indent=2)"
                        # Let's try our YAML converter first, it's cleaner for reading.
                        final_content = to_yaml_style(json_obj)
                    except Exception:
                        # Fallback to original content if parsing fails
                        pass

                outfile.write(f"--- START OF FILE: {rel_path} ---\n")
                outfile.write(final_content)
                if not final_content.endswith('\n'):
                    outfile.write('\n')
                outfile.write(f"--- END OF FILE: {rel_path} ---\n\n")

                # Store for JSON memory export (Node structure)
                memory_records.append({
                    "id": rel_path,
                    "timestamp": int(os.path.getmtime(file_path)),
                    "role": "file",
                    "content": final_content,
                    "source": rel_path
                })

            except Exception as e:
                print(f"Error processing '{rel_path}': {e}")

    # Save the combined memory records for Builder ingestion
    memory_file = os.path.join(project_root, "combined_memory.json")
    with open(memory_file, "w", encoding="utf-8") as f:
        json.dump(memory_records, f, indent=2, ensure_ascii=False)
    print(f"Memory records saved to '{memory_file}'.")

    print(f"\nAggregation complete. Corpus saved to '{output_file}'.")

def _parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Aggregate project code and docs for orchestration.")
    p.add_argument(
        "--out",
        "-o",
        default=None,
        help="Output file path (defaults to combined_text.txt in project root)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without writing the combined file",
    )
    return p.parse_args()

if __name__ == "__main__":
    args = _parse_cli()
    create_project_corpus(
        output_file=args.out,
        dry_run=args.dry_run,
    )