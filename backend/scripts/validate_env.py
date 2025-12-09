"""
Validate .env files for malformed keys and values.
Checks for keys containing whitespace or invalid characters and reports the file & line number.
Usage: python validate_env.py [path/to/envfile] ...
"""
import sys
import re
from pathlib import Path

ENV_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


def validate_env_file(p: Path) -> int:
    errs = 0
    if not p.exists():
        print(f"[WARN] File not found: {p}")
        return errs
    for i, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if '=' not in s:
            print(f"{p}:{i}: invalid - no '=' found")
            errs += 1
            continue
        key, _ = s.split('=', 1)
        key = key.strip()
        if not ENV_KEY_RE.match(key):
            print(f"{p}:{i}: invalid key: '{key}'")
            errs += 1
    return errs


def main():
    args = sys.argv[1:] or ["./.env", "./configs/.env", "./ece-core/.env"]
    total = 0
    for a in args:
        p = Path(a)
        total += validate_env_file(p)
    if total:
        print(f"\nTotal issues found: {total}")
        sys.exit(2)
    print("No issues found in .env files.")


if __name__ == '__main__':
    main()
