#!/usr/bin/env python3
"""
Import combined_text.txt into ECE_Core using the API and verify memory ingestion.

Usage:
  python scripts/import_and_verify.py --file combined_text.txt [--api http://127.0.0.1:8000] [--session import] [--max-tokens 3000] [--dry-run] [--verify query1,query2] [--ask "Tell me about Sybil"]

This script posts memory chunks to POST /memories and then validates with /memories/search and optional /chat.
"""

import argparse
import json
import os
import sys
import time
from typing import List

import requests

try:
    import tiktoken
except Exception:
    tiktoken = None


def count_tokens(text: str) -> int:
    if not text:
        return 0
    if tiktoken:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            return max(1, len(text) // 4)
    else:
        return max(1, len(text) // 4)


def chunk_text_by_tokens(text: str, max_tokens: int) -> List[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks = []
    current = []
    current_tokens = 0
    for line in lines:
        tokens = count_tokens(line)
        # if single line exceeds max_tokens, split roughly by characters
        if tokens > max_tokens and current_tokens == 0:
            # rough fallback split
            parts = [line[i:i+max_tokens*4] for i in range(0, len(line), max_tokens*4)]
            for p in parts:
                chunks.append(p.strip())
            continue
        if current_tokens + tokens > max_tokens and current:
            chunks.append("\n".join(current).strip())
            current = [line]
            current_tokens = tokens
        else:
            current.append(line)
            current_tokens += tokens
    if current:
        chunks.append("\n".join(current).strip())
    return chunks


def post_memory(api_base: str, category: str, content: str, tags=None, importance: int = 5, metadata=None):
    url = api_base.rstrip("/") + "/memories"
    payload = {
        "category": category or "import",
        "content": content,
        "tags": tags or [],
        "importance": importance,
        "metadata": metadata or {"source": "import_and_verify"}
    }
    r = requests.post(url, json=payload, timeout=60)
    return r


def search_memory(api_base: str, query: str, limit: int = 10):
    url = api_base.rstrip("/") + f"/memories/search?query={requests.utils.quote(query)}&limit={limit}"
    r = requests.get(url, timeout=30)
    if r.status_code == 200:
        return r.json()
    return None


def chat_with_agent(api_base: str, session_id: str, message: str):
    url = api_base.rstrip("/") + "/chat"
    data = {
        "session_id": session_id,
        "message": message
    }
    # If ECE requires API key, use env var ECE_API_KEY
    headers = {}
    api_key = os.environ.get("ECE_API_KEY") or os.environ.get("ECE_API_KEY__dummy")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    r = requests.post(url, json=data, headers=headers, timeout=60)
    return r


def main():
    parser = argparse.ArgumentParser(description="Import combined_text via ECE_Core API and verify")
    parser.add_argument("--file", required=True, help="Path to combined_text.txt")
    parser.add_argument("--api", default=os.environ.get("ECE_API_BASE", "http://127.0.0.1:8000"), help="API base URL")
    parser.add_argument("--session", default="import", help="Session ID to use for chat and context")
    parser.add_argument("--max-tokens", type=int, default=3000, help="Max tokens per chunk")
    parser.add_argument("--dry-run", action="store_true", help="Do not POST anything, only log chunks")
    parser.add_argument("--verify", help="Comma separated list of queries to verify (e.g., 'Sybil,MyProject')")
    parser.add_argument("--ask", help="A chat prompt to run after importing to validate knowledge (e.g. 'Tell me about Sybil')")
    parser.add_argument("--batch-size", type=int, default=10, help="Number of chunks to post per batch before sleeping")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between posts (seconds)")
    args = parser.parse_args()

    with open(args.file, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = chunk_text_by_tokens(text, args.max_tokens)
    print(f"Found {len(chunks)} chunks (max tokens {args.max_tokens})")

    if args.dry_run:
        for i, c in enumerate(chunks[:20], 1):
            print("--- chunk %d ---" % i)
            print(c[:200])
        print("Dry-run complete.")
        return

    # Post chunks in batches
    posted = 0
    for i, chunk in enumerate(chunks):
        # simple dedup: skip if empty
        if not chunk.strip():
            continue
        # metadata example
        metadata = {"source": "combined_text_import", "chunk_index": i}
        try:
            r = post_memory(args.api, category="import", content=chunk, tags=["imported"], importance=5, metadata=metadata)
            if r.status_code != 200:
                print(f"Failed to post chunk {i}: {r.status_code} {r.text}")
            else:
                posted += 1
                if posted % args.batch_size == 0:
                    print(f"Posted {posted} chunks; sleeping {args.delay} seconds")
                    time.sleep(args.delay)
        except Exception as e:
            print("Error posting chunk", i, e)
            time.sleep(1)

    print(f"Import finished. Posted {posted} chunks")

    # Verification part
    queries = [q.strip() for q in (args.verify or "Sybil").split(',') if q.strip()]
    for q in queries:
        print(f"Searching for '{q}'...")
        res = search_memory(args.api, q, limit=10)
        print(json.dumps(res, indent=2))

    if args.ask:
        print("Chatting with session to validate memory retrieval")
        resp = chat_with_agent(args.api, args.session, args.ask)
        if resp.status_code == 200:
            print("Chat response:", json.dumps(resp.json(), indent=2))
        else:
            print("Chat failed:", resp.status_code, resp.text)


if __name__ == '__main__':
    main()
