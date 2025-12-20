#!/usr/bin/env python3
"""CI doc check script (Sovereign Era).

Verifies the presence of critical spec files defined in specs/doc_policy.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    # 1. Check Core Specs (per specs/doc_policy.md Rule 3)
    expected = [
        REPO_ROOT / "specs" / "spec.md",
        REPO_ROOT / "specs" / "plan.md",
        REPO_ROOT / "specs" / "tasks.md",
        REPO_ROOT / "specs" / "doc_policy.md",
    ]
    
    missing = [str(p) for p in expected if not p.exists()]
    if missing:
        print("[FAIL] Missing core specification files:")
        for m in missing:
            print(f"  - {m}")
        return 2

    # 2. Check README
    readme = REPO_ROOT / "README.md"
    if not readme.exists():
        print("[FAIL] README.md not found")
        return 2

    text = readme.read_text(encoding="utf-8")
    lower = text.lower()
    
    # 3. Simple Content Check (Sovereign Context Engine)
    # We relax the strict "UTCP" check as architecture evolves.
    checks = [
        ("context engine", "Project name 'Context Engine' not found in README"),
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

    print("[OK] Sovereign Doc Checks Passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
