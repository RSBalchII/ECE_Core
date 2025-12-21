#!/usr/bin/env python3
"""
Root Reader: Aggregates content from relevant project files for orchestration.

This script scans the project directory and combines the content of source code,
configuration, and documentation files into a single text file (combined_text.txt).

It respects the current project structure:
- Root level scripts and docs
- tools/: Sovereign Core (JS/HTML/CSS)
- specs/: System Specifications
- scripts/: CI/Utility scripts
"""
import argparse
import os
from typing import List, Tuple

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

def get_allowed_files(project_root: str) -> List[Tuple[str, str]]:
    """
    Returns list of (file_path, section_name) for all relevant project files.
    """
    allowed_files = []
    
    # Extensions we care about
    code_exts = {'.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.bat', '.ps1', '.sh', '.yaml', '.yml'}
    
    # Directories to completely ignore
    ignored_dirs = {'.git', '.venv', 'browser_data', 'archive', '__pycache__', 'node_modules', '.github'}
    
    # Files to ignore
    ignored_files = {
        'package-lock.json', 
        'combined_text.txt', 
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
            if f in ignored_files:
                continue
            
            ext = os.path.splitext(f)[1].lower()
            if ext in code_exts:
                full_path = os.path.join(root, f)
                allowed_files.append((full_path, section))
                
    return allowed_files

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

                outfile.write(f"--- START OF FILE: {rel_path} ---\n")
                outfile.write(decoded_content)
                if not decoded_content.endswith('\n'):
                    outfile.write('\n')
                outfile.write(f"--- END OF FILE: {rel_path}---\n\n")

            except Exception as e:
                print(f"Error processing '{rel_path}': {e}")

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