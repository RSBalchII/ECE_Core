<#
PowerShell package build script for ECE_Core (Windows)

Usage:
  .\build_package.ps1

This will:
- Create a wheel + sdist using `python -m build` and place artifacts under `dist/`
#>
try {
  Write-Host "Building ECE_Core package..."
  python -m pip install --upgrade build hatchling
  python -m build
  Write-Host "Build complete. Artifacts in dist/"
} catch {
  Write-Error "Build failed: $_"
  exit 1
}
