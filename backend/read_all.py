#!/usr/bin/env python3
"""
Backend Reader: Aggregates content from backend allowed directories only.

According to the documentation policy, this script reads content from:
- Backend/: README.md
- Backend specs/: spec.md, plan.md, tasks.md
- Backend src/: All Python files in the src/ directory excluding tests

Excludes all other directories, generic boilerplate, and standard libraries.
"""
import argparse
import os
import chardet
from typing import List, Tuple


def find_backend_root(start_path: str | None = None) -> str:
    """
    Locate backend root by looking for backend-specific indicators
    """
    if start_path is None:
        start_path = os.path.abspath(__file__)

    path = os.path.abspath(start_path)
    if os.path.isfile(path):
        path = os.path.dirname(path)

    # Look for backend-specific indicators
    root_indicators = ("src", "specs", "README.md", "pyproject.toml")
    while True:
        if any(os.path.exists(os.path.join(path, ind)) for ind in root_indicators):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            # reached filesystem root, fall back to dirname of this script
            return os.path.dirname(path)
        path = parent


def _is_binary_filename(filename: str) -> bool:
    binary_exts = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".flac",
        ".mp3",
        ".mp4",
        ".pdf",
        ".exe",
        ".dll",
        ".class",
        ".so",
        ".o",
        ".pyc",
        ".whl",
        ".jar",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
    )
    return filename.lower().endswith(binary_exts)


def get_backend_allowed_files(backend_root: str) -> List[Tuple[str, str]]:
    """
    Returns list of (file_path, section_name) for all backend allowed files according to documentation policy.
    """
    allowed_files = []
    
    # Backend README
    backend_readme = os.path.join(backend_root, "README.md")
    if os.path.exists(backend_readme):
        allowed_files.append((backend_readme, "BACKEND_ROOT"))
    
    # Backend specs/
    specs_dir = os.path.join(backend_root, "specs")
    if os.path.exists(specs_dir):
        spec_files = [
            ("spec.md", "BACKEND_SPECS"),
            ("plan.md", "BACKEND_SPECS"),
            ("tasks.md", "BACKEND_SPECS"),
        ]
        for filename, section in spec_files:
            full_path = os.path.join(specs_dir, filename)
            if os.path.exists(full_path):
                allowed_files.append((full_path, section))
    
    # Backend src/ directory
    src_dir = os.path.join(backend_root, "src")
    if os.path.exists(src_dir):
        for root, dirs, files in os.walk(src_dir):
            # Remove virtual environment directories from search
            dirs[:] = [d for d in dirs if not d.startswith('.') or d in ['.vscode', '.github']]
            for f in files:
                if f.endswith('.py'):
                    full_path = os.path.join(root, f)
                    # Skip if path contains virtual environment indicators
                    if '.venv' in full_path or 'site-packages' in full_path or 'venv' in full_path:
                        continue
                    # Exclude test files and __init__.py to focus on core logic
                    if 'test' not in f.lower() and '__init__.py' != f:
                        allowed_files.append((full_path, "BACKEND_PYTHON"))
    
    return allowed_files


def create_backend_corpus(
    output_file: str | None = None,
    dry_run: bool = False,
):
    """
    Aggregates content from backend allowed files according to documentation policy
    """
    backend_root = find_backend_root()
    output_file = output_file or os.path.join(backend_root, "combined_text_backend.txt")

    print(f"Backend Root Detected: {backend_root}")
    print("Reading from allowed backend directories according to documentation policy...")

    allowed_files = get_backend_allowed_files(backend_root)

    if not allowed_files:
        print(f"No allowed files found in '{backend_root}'.")
        return

    print(f"Found {len(allowed_files)} allowed backend files to process according to documentation policy.")

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

    print(f"\nBackend corpus aggregation complete. All allowed content saved to '{output_file}'.")


def _parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Aggregate content from backend allowed directories only.")
    p.add_argument(
        "--out",
        "-o",
        default=None,
        help="Output file path (defaults to combined_text_backend.txt in backend)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without writing the combined file",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_cli()
    
    create_backend_corpus(
        output_file=args.out,
        dry_run=args.dry_run,
    )