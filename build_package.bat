@echo off
REM ECE Packaging Build Script for Windows
REM This script packages the ECE application into a single executable using PyInstaller

setlocal

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller is not installed. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

REM Check if the spec file exists
if not exist "ece_app.spec" (
    echo ece_app.spec file not found. Creating a basic spec file...
    
    REM Create a basic spec file if it doesn't exist
    python -c "
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
)

REM Run PyInstaller with the spec file
echo Building ECE application executable...
pyinstaller ece_app.spec --clean

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo Build completed successfully!
echo The executable is located in the 'dist' folder as 'ece_app.exe'
echo You can run the application with: dist\ece_app.exe

REM Create a convenience batch file to run the packaged application
echo @echo off > run_packaged_ece.bat
echo REM Run the packaged ECE application >> run_packaged_ece.bat
echo echo Starting External Context Engine from packaged executable... >> run_packaged_ece.bat
echo dist\ece_app.exe >> run_packaged_ece.bat
echo echo. >> run_packaged_ece.bat
echo echo ECE has stopped. Press any key to exit. >> run_packaged_ece.bat
echo pause >> run_packaged_ece.bat

echo.
echo A convenience script 'run_packaged_ece.bat' has been created to run the packaged application.
echo.

pause