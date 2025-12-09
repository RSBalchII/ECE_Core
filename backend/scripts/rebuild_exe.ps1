<#
Rebuild the ECE_Core desktop exe using PyInstaller.

Usage:
  # Windows PowerShell
  Set-Location -Path C:\Users\rsbiiw\Projects\ECE_Core
  .\scripts\rebuild_exe.ps1

This script will:
  - Install build dependencies into the active Python env if needed
  - Build the exe using the tracked spec file `ece.spec`
  - Output the packed exe to the `dist/` folder

Note: Windows Defender or other AV tooling may cause corruption of the built exe at runtime.
Recommend adding an exclusion for the `dist\` directory while packaging/testing.
#>

param(
  [string]$PythonExe = "C:\\Users\\rsbiiw\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
  [string]$SpecFile = "ece.spec"
)

Write-Host "Rebuilding ECE_Core exe using PyInstaller (spec: $SpecFile)"

# Ensure PyInstaller is installed
& $PythonExe -m pip install -U pyinstaller

# Build
& $PythonExe -m PyInstaller $SpecFile --noconfirm --log-level=INFO

Write-Host "Build finished. Verify the dist folder for the new exe. If you see a 'Failed to extract' error at runtime, ensure Windows Defender isn't quarantining files or try running with the 'upx' option disabled in the spec (default in repo)."

Write-Host "Tip: To avoid permission issues, run PowerShell as Administrator when re-running PyInstaller and temporarily disable real-time AV scanning for the build folder."
