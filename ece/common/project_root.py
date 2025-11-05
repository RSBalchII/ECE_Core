"""
Reliable project root detection that works in all environments.

This module provides functions to detect the project root directory
consistently across different execution contexts (development, PyInstaller,
containers, etc.).
"""

from pathlib import Path
import sys


def get_project_root():
    """
    Reliable project root detection that works in all environments.

    Returns:
        Path: The project root directory
    """
    # Method 1: Check for marker file in parent directories
    current = Path.cwd()
    for _ in range(10):  # Limit search to prevent infinite loops
        if (current / ".project_root").exists():
            return current
        if current == current.parent:  # Reached the root of the filesystem
            break
        current = current.parent

    # Method 2: Fallback to script location
    # This works when running scripts directly
    script_dir = (
        Path(__file__).resolve().parent.parent.parent
    )  # ece/common/ -> ece/ -> project root
    if (script_dir / ".project_root").exists():
        return script_dir

    # Method 3: Fallback to current working directory
    # This might not work in all contexts, but it's our last resort
    print(
        f"Warning: Could not find .project_root marker file. Using current directory: {Path.cwd()}",
        file=sys.stderr,
    )
    return Path.cwd()


def get_config_path():
    """
    Get the path to the config file with proper fallbacks.

    Returns:
        Path: Path to config.yaml
    """
    root = get_project_root()
    for config_name in ["config.yaml", "config_executable.yaml", "config.default.yaml"]:
        config_path = root / config_name
        if config_path.exists():
            return config_path

    # If no config file exists, return the path to the default location
    return root / "config.yaml"


def get_models_dir():
    """
    Get the path to the models directory with proper fallbacks.

    Returns:
        Path: Path to the models directory
    """
    root = get_project_root()
    models_dirs = [
        root / "models",
        root / ".." / "models",  # In case we're in a subdirectory
    ]

    for models_dir in models_dirs:
        if models_dir.exists():
            return models_dir.resolve()

    # If models directory doesn't exist, create it
    models_dir = root / "models"
    models_dir.mkdir(exist_ok=True)
    return models_dir


def get_logs_dir():
    """
    Get the path to the logs directory with proper fallbacks.

    Returns:
        Path: Path to the logs directory
    """
    root = get_project_root()
    logs_dirs = [
        root / "logs",
        root / ".." / "logs",  # In case we're in a subdirectory
    ]

    for logs_dir in logs_dirs:
        if logs_dir.exists():
            return logs_dir.resolve()

    # If logs directory doesn't exist, create it
    logs_dir = root / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir
