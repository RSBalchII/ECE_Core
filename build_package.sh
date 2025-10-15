#!/bin/bash

# ECE Packaging Build Script for Linux/macOS
# This script packages the ECE application into a single executable using PyInstaller

set -e  # Exit immediately if a command exits with a non-zero status

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "PyInstaller is not installed. Installing..."
    pip3 install pyinstaller || {
        echo "Failed to install PyInstaller."
        exit 1
    }
fi

# Check if the spec file exists
if [ ! -f "ece_app.spec" ]; then
    echo "ece_app.spec file not found. Creating a basic spec file..."
    
    # Create a basic spec file if it doesn't exist
    python3 -c "
import os
spec_content = '''# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['run_all_agents.py'],
    pathex=[os.path.dirname(os.path.abspath('run_all_agents.py'))],
    binaries=[],
    datas=[('config.yaml', '.'), ('poml', 'poml')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ece_app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)
'''
with open('ece_app.spec', 'w') as f:
    f.write(spec_content)
"
fi

# Run PyInstaller with the spec file
echo "Building ECE application executable..."
pyinstaller ece_app.spec --clean

if [ $? -ne 0 ]; then
    echo "Build failed."
    exit 1
fi

echo "Build completed successfully!"
echo "The executable is located in the 'dist' folder as 'ece_app'"
echo "You can run the application with: ./dist/ece_app"

# Create a convenience script to run the packaged application
cat > run_packaged_ece.sh << 'EOF'
#!/bin/bash
# Run the packaged ECE application
echo "Starting External Context Engine from packaged executable..."
./dist/ece_app
echo
echo "ECE has stopped."
EOF

chmod +x run_packaged_ece.sh

echo
echo "A convenience script 'run_packaged_ece.sh' has been created to run the packaged application."