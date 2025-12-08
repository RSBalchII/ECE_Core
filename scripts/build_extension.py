import json
import os
import zipfile
from pathlib import Path

def build_extension():
    # Paths
    project_root = Path(__file__).parent.parent
    extension_dir = project_root / "Context-Engine" / "extension"
    dist_dir = project_root / "dist"
    manifest_path = extension_dir / "manifest.json"

    # 1. Read Manifest for Version
    if not manifest_path.exists():
        print(f"Error: Manifest not found at {manifest_path}")
        return

    with open(manifest_path, "r") as f:
        manifest = json.load(f)
        version = manifest.get("version", "0.0.0")
        name = manifest.get("name", "extension").replace(" ", "_").lower()

    # 2. Create Dist Directory
    dist_dir.mkdir(exist_ok=True)
    zip_filename = f"{name}_v{version}.zip"
    zip_path = dist_dir / zip_filename

    print(f"Building {zip_filename}...")

    # 3. Create Zip Archive
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(extension_dir):
            # Filter directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            
            for file in files:
                if file.startswith("."):
                    continue
                
                file_path = Path(root) / file
                # Calculate arcname (relative path inside zip)
                arcname = file_path.relative_to(extension_dir)
                
                print(f"  Adding: {arcname}")
                zipf.write(file_path, arcname)

    print(f"\nBuild Complete: {zip_path}")
    print(f"Size: {zip_path.stat().st_size / 1024:.2f} KB")

if __name__ == "__main__":
    build_extension()
