import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"


def test_build_package_unix():
    # Try the Unix build script (skip on Windows)
    if sys.platform.startswith("win"):
        return
    script = ROOT / "scripts" / "build_package.sh"
    if not script.exists():
        raise AssertionError("build_package.sh missing")
    subprocess.run(["bash", str(script)], check=True, cwd=ROOT)
    assert DIST.exists(), "dist/ not created"
    # At least one artifact
    files = list(DIST.glob("*"))
    assert len(files) > 0


def test_build_package_ps1_on_windows():
    # Windows PowerShell build
    if not sys.platform.startswith("win"):
        return
    script = ROOT / "scripts" / "build_package.ps1"
    assert script.exists(), "PowerShell build script missing"
    subprocess.run(["powershell", "-File", str(script)], check=True, cwd=ROOT)
    assert DIST.exists()
    files = list(DIST.glob("*"))
    assert len(files) > 0
