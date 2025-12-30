# Standard 001: Windows Console Encoding

## What Happened?
The Python Bridge (`webgpu_bridge.py`) crashed immediately upon launch on Windows 11. The error was `UnicodeEncodeError: 'charmap' codec can't encode character...`.

## The Cost
- 3 failed integration attempts.
- "Integration Hell" state requiring full manual intervention.
- Bridge stability compromised during demos.

## The Rule
1. **Explicit Encoding:** All Python scripts outputting to stdout must explicitly handle encoding.
2. **The Fix:** Include this snippet at the top of all entry points:
   ```python
   import sys
   if sys.platform == "win32":
       sys.stdout.reconfigure(encoding='utf-8')
   ```

3. **Validation:** CI/CD or startup scripts must verify the bridge launches without encoding errors.