import io
import os
import importlib.util
from pathlib import Path


def _load_read_all_module(module_path: Path):
    spec = importlib.util.spec_from_file_location("read_all", str(module_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_create_full_corpus_filters_out_build_and_node_modules(tmp_path):
    # Create directory tree
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello')\n")

    node_dir = tmp_path / "node_modules" / "somepkg"
    node_dir.mkdir(parents=True)
    (node_dir / "index.js").write_text("console.log('lib')\n")

    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "artifact.js").write_text("minified()\n")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "README.md").write_text("# Project docs\n\nSome docs")

    output_file = tmp_path / "combined_text.txt"

    # Load the module from the project root file directly
    read_all_mod = _load_read_all_module(Path(os.getcwd()) / "read_all.py")
    create_full_corpus_recursive = read_all_mod.create_full_corpus_recursive

    # Run script with the temporary root
    create_full_corpus_recursive(root_dir_to_scan=str(tmp_path), output_file=str(output_file))

    assert output_file.exists()
    combined_text = output_file.read_text(encoding="utf-8")
    # main.py should be included
    assert "print('hello')" in combined_text
    # README.md should be included
    assert "# Project docs" in combined_text
    # node_modules/index.js and build artifact should NOT be included
    assert "console.log('lib')" not in combined_text
    assert "minified()" not in combined_text
