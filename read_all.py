#!/usr/bin/env python3
"""
Project Root Reader: Aggregates content from allowed directories only.

Updated to reflect the new project structure:
- Root: README.md, CHANGELOG.md
- Backend/: ECE Core (Python)
- Anchor-Chat/: New TUI (Python)
- Extension/: Browser Extension (JS/HTML/CSS)
- Specs/: Documentation

Excludes archived folders and generic boilerplate.
"""
import argparse
import os
import chardet
from typing import Iterable, List, Tuple


def find_project_root(start_path: str | None = None) -> str:
    """
    Locate project root by looking for indicators like .git, pyproject.toml, README.md
    """
    if start_path is None:
        start_path = os.path.abspath(__file__)

    path = os.path.abspath(start_path)
    if os.path.isfile(path):
        path = os.path.dirname(path)

    root_indicators = (".git", "pyproject.toml", "package.json", "README.md")
    while True:
        if any(os.path.exists(os.path.join(path, ind)) for ind in root_indicators):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            # reached filesystem root, fall back to cwd
            return os.getcwd()
        path = parent


def get_allowed_files(project_root: str) -> List[Tuple[str, str]]:
    """
    Returns list of (file_path, section_name) for all allowed files according to documentation policy.
    """
    allowed_files = []
    
    # Root level allowed files
    root_files = [
        ("README.md", "ROOT_PROJECT"),
        ("CHANGELOG.md", "ROOT_PROJECT"),
    ]
    for filename, section in root_files:
        full_path = os.path.join(project_root, filename)
        if os.path.exists(full_path):
            allowed_files.append((full_path, section))
    
    # Root specs/ directory
    root_specs_dir = os.path.join(project_root, "specs")
    if os.path.exists(root_specs_dir):
        for f in os.listdir(root_specs_dir):
            if f.endswith(".md"):
                allowed_files.append((os.path.join(root_specs_dir, f), "ROOT_SPECS"))
    
    # Backend (ECE Core)
    backend_dir = os.path.join(project_root, "backend")
    if os.path.exists(backend_dir):
        # Backend Root Files (launchers, config, readme)
        for f in os.listdir(backend_dir):
            if f in ["README.md", "config.yaml", "requirements.txt"] or (f.endswith(".py") and not f.startswith("test_")):
                 allowed_files.append((os.path.join(backend_dir, f), "BACKEND_ROOT"))

        # Backend Source
        src_dir = os.path.join(backend_dir, "src")
        if os.path.exists(src_dir):
            for root, dirs, files in os.walk(src_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                for f in files:
                    if f.endswith('.py') and not f.startswith('test_'):
                        allowed_files.append((os.path.join(root, f), "BACKEND_SRC"))
    
        # Backend specs/
        backend_specs_dir = os.path.join(backend_dir, "specs")
        if os.path.exists(backend_specs_dir):
            for f in os.listdir(backend_specs_dir):
                if f.endswith(".md"):
                    allowed_files.append((os.path.join(backend_specs_dir, f), "BACKEND_SPECS"))
    
    # Anchor Chat (New TUI)
    anchor_chat_dir = os.path.join(project_root, "anchor-chat")
    if os.path.exists(anchor_chat_dir):
        for root, dirs, files in os.walk(anchor_chat_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for f in files:
                if f.endswith(('.py', '.txt', '.md')):
                    allowed_files.append((os.path.join(root, f), "ANCHOR_CHAT"))

    # Extension (Browser)
    extension_dir = os.path.join(project_root, "extension")
    if os.path.exists(extension_dir):
        for root, dirs, files in os.walk(extension_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.endswith(('.js', '.html', '.json', '.css', '.md')):
                    allowed_files.append((os.path.join(root, f), "EXTENSION"))
    
    return allowed_files


def create_project_corpus(
    output_file: str | None = None,
    include_custom_code: bool = True,
    dry_run: bool = False,
):
    """
    Aggregates content from allowed project files according to documentation policy
    """
    project_root = find_project_root()
    output_file = output_file or os.path.join(project_root, "combined_text.txt")

    print(f"Project Root Detected: {project_root}")
    print("Reading from allowed directories according to documentation policy...")

    allowed_files = get_allowed_files(project_root)

    if not allowed_files:
        print(f"No allowed files found in '{project_root}'.")
        return

    print(f"Found {len(allowed_files)} allowed files to process.")

    if dry_run:
        print(f"Dry run enabled — would process {len(allowed_files)} files:")
        for file_path, section in allowed_files:
            print(f"  - {file_path} ({section})")
        return

    with open(output_file, "w", encoding="utf-8") as outfile:
        for file_path, section in allowed_files:
            print(f"Processing '{file_path}' in section {section}...")
            try:
                with open(file_path, "rb") as raw_file:
                    raw_data = raw_file.read()
                if not raw_data:
                    continue
                # Use chardet to guess the encoding, but default to utf-8
                encoding = chardet.detect(raw_data)["encoding"] or "utf-8"

                # Decode using the detected encoding, replacing any errors
                decoded_content = raw_data.decode(encoding, errors="replace")

                outfile.write(f"--- START OF FILE: {file_path} (Section: {section}) ---\n\n")
                outfile.write(decoded_content + "\n\n")
                outfile.write(f"--- END OF FILE: {file_path} ---\n\n")

            except Exception as e:
                print(f"An unexpected error occurred with file '{file_path}': {e}")

    print(f"\nCorpus aggregation complete. All allowed content saved to '{output_file}'.")


def _parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Aggregate content from allowed project directories only.")
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
