import os
import sys
from pathlib import Path

# Add the project root and venv paths to Python path
project_root = Path(r"C:\Users\rsbiiw\Projects\External-Context-Engine-ECE")
venv_site_packages = project_root / ".venv" / "Lib" / "site-packages"

print(f"Project root: {project_root}")
print(f"Site packages path exists: {venv_site_packages.exists()}")
print(f"Python executable: {sys.executable}")

# Check for UTCP-related directories in site-packages
if venv_site_packages.exists():
    utcp_dirs = [
        d
        for d in venv_site_packages.iterdir()
        if d.is_dir() and "utcp" in d.name.lower()
    ]
    print(f"UTCP-related packages found in site-packages: {utcp_dirs}")

    # Check in general packages too
    all_dirs = [
        d
        for d in venv_site_packages.iterdir()
        if d.is_dir() and "utcp" in d.name.lower()
    ]
    print(f"All UTCP-related packages: {all_dirs}")

# Try importing
import importlib.util

try:
    # Check if utcp module exists
    spec = importlib.util.find_spec("utcp")
    if spec is not None:
        print("UTCP module is available for import")
        print(
            f"UTCP module location: {spec.origin if hasattr(spec, 'origin') else spec.origin}"
        )
    else:
        print("UTCP module is NOT available for import")
except Exception as e:
    print(f"Error checking UTCP spec: {e}")

# Try importing UTCP client
try:
    print("Attempting to import UTCP client...")
    from utcp.utcp_client import UtcpClient

    print("✓ UTCP client imported successfully")
except ImportError as e:
    print(f"✗ Failed to import UTCP client: {e}")
except Exception as e:
    print(f"✗ Unexpected error importing UTCP client: {e}")

print("Script completed successfully")
