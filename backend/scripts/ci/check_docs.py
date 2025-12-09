#!/usr/bin/env python3
"""CI doc check script.

Verifies the presence of vision, references, and UX docs, and checks README contains the project mission & UTCP preference.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    expected = [
        REPO_ROOT / "specs" / "vision.md",
        REPO_ROOT / "specs" / "references.md",
        REPO_ROOT / "specs" / "UX.md",
    ]
    missing = [str(p) for p in expected if not p.exists()]
    if missing:
        print("[FAIL] Missing documentation files:")
        for m in missing:
            print(f"  - {m}")
        return 2

    readme = REPO_ROOT / "README.md"
    if not readme.exists():
        print("[FAIL] README.md not found")
        return 2

    text = readme.read_text(encoding="utf-8")
    lower = text.lower()
    checks = [
        ("executive cognitive enhancement", "project mission 'Executive Cognitive Enhancement' not mentioned in README"),
        ("utcp", "UTCP not mentioned in README; ensure UTCP is documented as primary tool protocol"),
    ]
    failed = []
    for token, msg in checks:
        if token not in lower:
            failed.append(msg)
    if failed:
        print("[FAIL] README checks failed:")
        for f in failed:
            print(f"  - {f}")
        return 2

    print("[OK] docs & README check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
