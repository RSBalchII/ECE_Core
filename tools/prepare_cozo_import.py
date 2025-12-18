#!/usr/bin/env python3
"""
Prepare a CozoDB import payload from an existing combined_memory.json file.
Usage:
  python tools/prepare_cozo_import.py [input_path] [output_path]
If input_path is omitted the script will search likely locations.
"""
import json
import os
import sys
from pathlib import Path

# Defaults
POSSIBLE_INPUTS = [
    Path("combined_memory.json")
]
DEFAULT_OUTPUT = Path("cozo_import_memory.json")

def find_input(path_arg=None):
    if path_arg:
        p = Path(path_arg)
        if p.exists():
            return p
        else:
            print(f"❌ Specified input not found: {p}")
            return None
    for p in POSSIBLE_INPUTS:
        if p.exists():
            return p
    # fallback: search workspace for first combined_memory.json
    for p in Path('.').rglob('combined_memory.json'):
        return p
    return None


def normalize_record(rec):
    # Ensure the fields Cozo expects. Return None to skip invalid records.
    uid = rec.get("id") or rec.get("uid") or rec.get("uuid") or None
    if not uid:
        # try deterministic id from source+timestamp
        src = rec.get("source") or rec.get("file") or ""
        ts = rec.get("timestamp") or rec.get("created_at") or 0
        uid = f"auto:{abs(hash(src + str(ts)))}"
    try:
        uid = str(uid)
    except Exception:
        uid = str(uid)

    try:
        ts = int(rec.get("timestamp", rec.get("created_at", 0)) or 0)
    except Exception:
        try:
            ts = int(float(rec.get("timestamp", 0)))
        except Exception:
            ts = 0

    role = str(rec.get("role", "system"))
    content = rec.get("content", "")
    if not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False)
        except Exception:
            content = str(content)
    # cap content size to be safe
    MAX_CONTENT = 200_000
    if len(content) > MAX_CONTENT:
        content = content[:MAX_CONTENT]

    source = rec.get("source", rec.get("file", "historical_import"))
    try:
        source = str(source)
    except Exception:
        source = "historical_import"

    embedding = rec.get("embedding", None)
    # Keep embedding as-is if present and looks like a list of numbers
    if isinstance(embedding, list):
        # Optionally validate length later; leave as-is
        pass
    else:
        embedding = None

    return [uid, ts, role, content, source, embedding]


def main():
    input_arg = sys.argv[1] if len(sys.argv) > 1 else None
    output_arg = sys.argv[2] if len(sys.argv) > 2 else None

    inp = find_input(input_arg)
    if not inp:
        print("❌ Could not find a combined_memory.json file. Provide the path as the first argument.")
        return 1

    out = Path(output_arg) if output_arg else DEFAULT_OUTPUT

    print(f"Reading {inp}...")
    try:
        raw = json.loads(inp.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return 1

    if not isinstance(raw, list):
        print("❗ Warning: input root is not a list. Attempting to find list under 'records' or 'data'.")
        if isinstance(raw, dict):
            if 'records' in raw and isinstance(raw['records'], list):
                raw = raw['records']
            elif 'data' in raw and isinstance(raw['data'], list):
                raw = raw['data']
            else:
                print("❌ Could not find the expected list of records in input JSON.")
                return 1

    print(f"Found {len(raw)} records. Normalizing and formatting...")

    rows = []
    for rec in raw:
        nr = normalize_record(rec)
        if nr is None:
            continue
        rows.append(nr)

    payload = {
        "relations": [
            {
                "name": "memory",
                "headers": ["id", "timestamp", "role", "content", "source", "embedding"],
                "rows": rows,
            }
        ]
    }

    print(f"Writing {len(rows)} rows to {out}...")
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print("✅ Done. You can now drag 'cozo_import_memory.json' into the Builder or use the console import helper.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
