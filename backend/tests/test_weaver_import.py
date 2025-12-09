import importlib
import os
import sys


def test_repair_script_files_and_packages_exist():
    # Verify that file exists
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    repair_module_path = os.path.join(repo_root, 'scripts', 'neo4j', 'repair', 'repair_missing_links_similarity_embeddings.py')
    assert os.path.exists(repair_module_path), f"Repair script not found at {repair_module_path}"


def test_scripts_package_importable():
    # Ensure that the 'scripts' and nested packages are importable
    # Add repo root to sys.path to mimic runtime invocation
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    importlib.import_module('scripts')
    importlib.import_module('scripts.neo4j')
    importlib.import_module('scripts.neo4j.repair')
    # Verify the wrapper module is importable and exposes run_repair
    from src.maintenance import repair as repair_wrapper
    assert hasattr(repair_wrapper, 'run_repair'), 'repair wrapper missing run_repair'