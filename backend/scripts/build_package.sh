#!/usr/bin/env bash
set -euo pipefail
echo "Building ECE_Core package (Unix)"
python -m pip install --upgrade build hatchling
python -m build
echo "Build artifacts in dist/"
