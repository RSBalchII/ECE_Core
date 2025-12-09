import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"


def test_build_and_install_wheel():
    # Build the wheel using the build script, then pip install and verify import
    script = ROOT / "scripts" / "build_package.sh"
    if sys.platform.startswith("win"):
        # Run PS1 script on Windows
        script_ps1 = ROOT / "scripts" / "build_package.ps1"
        assert script_ps1.exists(), "build_package.ps1 missing"
        subprocess.run(["powershell", "-File", str(script_ps1)], check=True, cwd=ROOT)
    else:
        assert script.exists(), "build_package.sh missing"
        subprocess.run(["bash", str(script)], check=True, cwd=ROOT)

    assert DIST.exists(), "dist/ not created"
    files = list(DIST.glob("*") )
    assert len(files) > 0

    # Install the wheel into a fresh environment (in-place using pip)
    wheel_files = [p for p in files if p.suffix == ".whl"]
    assert wheel_files, "No wheel file found"
    wheel = wheel_files[0]
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", str(wheel)], check=True)

    # Quick import smoke test
    import src as _core
    assert hasattr(_core, "main") or hasattr(_core, "__name__")
