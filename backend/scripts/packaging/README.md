Packaging troubleshooting
==========================

When running a PyInstaller-built exe, you may encounter extraction errors similar to:

    [PYI-46504:ERROR] Failed to extract PIL\_avif.cp311-win_amd64.pyd: decompression resulted in return code -1!

What causes this?
- UPX compression: Some binary extensions (compiled .pyd files like `PIL._avif`) don't always decompress reliably on Windows, especially if UPX is used to compress them at build time.
- Antivirus (Windows Defender): Real-time scans may quarantine or modify files as they are extracted, causing decompression or checksum problems.
- Corrupted build: The generated dist/ exe or temporary extraction was corrupted during packaging.

Quick fixes you can try
-----------------------
1) Run the server from source temporarily (fastest to continue debugging):
   ```powershell
   Set-Location -Path C:\Users\rsbiiw\Projects\ECE_Core
   # Optionally set env var in this shell for the dev server
   $env:NEO4J_PASSWORD = 'your_real_password'
   python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
   ```

2) Rebuild the exe without UPX compression:
   ```powershell
   # Run from repo root as Administrator
   .\scripts\rebuild_exe.ps1
   ```

3) Add Defender/AV exception temporarily (avoid quarantining build files):
   ```powershell
   # Use PowerShell as Admin
   Set-MpPreference -ExclusionPath "C:\Users\rsbiiw\Projects\ECE_Core\dist"
   # or exclude the exact exe:
   Set-MpPreference -ExclusionProcess "C:\Users\rsbiiw\Projects\ECE_Core\dist\ECE_Core.exe"
   ```

4) Exclude the PIL.avif plugin or avoid packaging the avif plugin if it's not required.
   - If you don't need AVIF: `pip uninstall pillow-avif-plugin` from the build env or exclude `PIL._avif` in the spec file `excludes` list.

5) Check for build file corruption (rebuild from scratch and cat the archive contents):
   - Delete `build/` and `dist/` directories, run the `rebuild_exe.ps1` script and try again.

Persistent fixes
-----------------
- The spec file `ece.spec` is already configured in the repo to set `upx=False` to avoid UPX issues. If the exe still fails, rebuild and ensure no AV interference.
- Consider excluding specific pyd files from the bundle or add them as `binaries` explicitly so they're not compressed by UPX.

If you want me to rebuild the exe with a different set of packaging options or to further edit `ece.spec`, tell me which packaging behavior you prefer (e.g., `exclude pillow-avif` or `upx=True but exclude avif binary`).
