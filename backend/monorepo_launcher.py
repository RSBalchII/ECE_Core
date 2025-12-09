"""Monorepo launcher

Opens ECE_Core in a new terminal window and then launches Anchor CLI in the current terminal.

Usage:
  python monorepo_launcher.py

This script is intended for local debugging. When creating a single bundled exe later,
this file can be used as the entrypoint.
"""
import os
import subprocess
import sys

base_dir = os.path.dirname(__file__)
# Support legacy layout (ECE_Core at repo root) or new layout (ECE-System/ECE_Core)
if os.path.exists(os.path.join(base_dir, "ECE_Core")):
    ECE_DIR = os.path.join(base_dir, "ECE_Core")
elif os.path.exists(os.path.join(base_dir, "ECE-System", "ECE_Core")):
    ECE_DIR = os.path.join(base_dir, "ECE-System", "ECE_Core")
else:
    ECE_DIR = os.path.join(base_dir, "ECE_Core")

if os.path.exists(os.path.join(base_dir, "anchor")):
    ANCHOR_DIR = os.path.join(base_dir, "anchor")
elif os.path.exists(os.path.join(base_dir, "ECE-System", "anchor")):
    ANCHOR_DIR = os.path.join(base_dir, "ECE-System", "anchor")
else:
    ANCHOR_DIR = os.path.join(base_dir, "anchor")

def open_new_powershell(cmd: str, cwd: str | None = None) -> subprocess.Popen:
    """Open a new PowerShell window and run the given command there.

    On Windows we use 'start' via cmd.exe to spawn a new window.
    """
    # Build the command to run in the new window
    # Use cmd.exe /c start powershell -NoExit -Command "..."
    escaped = cmd.replace('"', '\\"')
    full = f'cmd.exe /C start powershell -NoExit -Command "{escaped}"'
    return subprocess.Popen(full, cwd=cwd, shell=True)

def main():
    # 1) Start ECE_Core in a new terminal window
    ece_cmd = "& './start.bat'" if os.name == 'nt' else "./start.bat"
    if not os.path.exists(ECE_DIR):
        print(f"WARN: ECE_Core directory not found at {ECE_DIR}")
    else:
        print("Starting ECE_Core in a new terminal window...")
        open_new_powershell(ece_cmd, cwd=ECE_DIR)

    # 2) Start Anchor CLI in the current terminal
    anchor_entry = os.path.join(ANCHOR_DIR, "anchor.py")
    if not os.path.exists(anchor_entry):
        print(f"ERROR: Anchor entry not found at {anchor_entry}")
        sys.exit(1)

    print("Launching Anchor CLI in this terminal...")
    # Use Python executable that's running this script
    os.execv(sys.executable, [sys.executable, anchor_entry])

if __name__ == '__main__':
    main()
