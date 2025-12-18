from pathlib import Path
import time

log_file = Path("logs/server.log")
print(f"Reading {log_file.absolute()}")

try:
    with log_file.open('r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        print(f"Read {len(content)} chars")
        print(f"First 100 chars: {content[:100]}")
except Exception as e:
    print(f"Error: {e}")
