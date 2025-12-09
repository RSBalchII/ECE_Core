#!/usr/bin/env python3
"""
Import combined_text.txt into ECE_Core via the /chat endpoint and verify memory ingestion.

Usage:
  python scripts/import_via_chat.py --file combined_text.txt [--api http://127.0.0.1:8000] [--session import] [--chunk-size 1000] [--dry-run] [--verify query1,query2] [--ask "Tell me about Sybil"]

This script posts text chunks to POST /chat and then validates memory ingestion using /memories/search and /memories.
"""

import argparse
import json
import os
import sys
import time
from typing import List

import requests
import signal
from requests.exceptions import RequestException, ReadTimeout, ConnectionError

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


def post_chat(api_base: str, session_id: str, message: str, system_prompt: str|None = None, timeout: int = 120):
    url = api_base.rstrip("/") + "/chat"
    payload = {
        "session_id": session_id,
        "message": message,
    }
    if system_prompt is not None:
        payload["system_prompt"] = system_prompt
    headers = {}
    api_key = os.environ.get("ECE_API_KEY") or os.environ.get("ECE_API_KEY__dummy")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    return r


def search_memory(api_base: str, query: str, limit: int = 10):
    url = api_base.rstrip("/") + f"/memories/search?query={requests.utils.quote(query)}&limit={limit}"
    r = requests.get(url, timeout=30)
    if r.status_code == 200:
        return r.json()
    return None


def check_api_health(api_base: str, timeout=5):
    try:
        r = requests.get(api_base.rstrip('/') + '/health', timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def make_memory_payload(chunk: str, index: int):
    return {
        "category": "import",
        "content": chunk,
        "tags": ["imported"],
        "importance": 5,
        "metadata": {"source": "import_via_chat", "chunk_index": index}
    }


def main():
    parser = argparse.ArgumentParser(description="Import combined_text via ECE_Core /chat endpoint and verify")
    parser.add_argument("--file", required=True, help="Path to combined_text.txt")
    parser.add_argument("--api", default=os.environ.get("ECE_API_BASE", "http://127.0.0.1:8000"), help="API base URL")
    parser.add_argument("--session", default="import", help="Session ID to use for chat and context")
    parser.add_argument("--chunk-size", type=int, default=3000, help="Max tokens per chunk")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of chunks to process (0 for no limit)")
    parser.add_argument("--dry-run", action="store_true", help="Do not POST anything, only log chunks")
    parser.add_argument("--force", action="store_true", help="Force add each chunk as a memory via POST /memories in addition to /chat (ensures persistence)")
    parser.add_argument("--verify", help="Comma separated list of queries to verify (e.g., 'Sybil,MyProject')")
    parser.add_argument("--ask", help="A chat prompt to run after importing to validate knowledge (e.g. 'Tell me about Sybil')")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of chunks to POST before sleeping")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between posts (seconds)")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout (seconds) for POST requests to the API endpoints")
    parser.add_argument("--resume", action="store_true", help="Resume a previous import run (state file) and skip already-posted chunks")
    parser.add_argument("--only-memories", action="store_true", help="Only POST to /memories (no /chat) to avoid LLM usage and force persistence)")
    parser.add_argument("--auto-fallback", action="store_true", help="If /chat fails, automatically fall-back to POST /memories for persistence")
    args = parser.parse_args()

    print(f"Using API base: {args.api}")
    if not check_api_health(args.api):
        print(f"Warning: API at {args.api} does not respond to /health - check port or server status.")
    if not os.path.exists(args.file):
        print(f"File not found: {args.file}")
        return

    with open(args.file, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = chunk_text_by_tokens(text, args.chunk_size)
    print(f"Found {len(chunks)} chunks (max tokens {args.chunk_size})")

    if args.dry_run:
        for i, c in enumerate(chunks[:20], 1):
            print("--- chunk %d ---" % i)
            print(c[:200])
        print("Dry-run complete.")
        return

    posted = 0
    stop_requested = False
    sigint_count = 0

    def _handle_sigint(sig, frame):
        nonlocal stop_requested, sigint_count
        sigint_count += 1
        if sigint_count == 1:
            print("\nSIGINT received - will exit after current chunk or retry completes; press Ctrl+C again to force immediate exit")
            stop_requested = True
        else:
            print("\nSecond SIGINT received - forcing immediate exit")
            sys.exit(1)
    signal.signal(signal.SIGINT, _handle_sigint)
    # state file to resume progress
    state_file = os.path.join(os.path.dirname(__file__), 'import_via_chat_state.json')
    last_completed = -1
    last_successful = None
    if args.resume and os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as sf:
                state = json.load(sf)
                last_completed = int(state.get('last_completed_chunk', -1))
                print(f"Resuming from chunk index {last_completed + 1}")
                last_successful = last_completed
        except Exception as e:
            print(f"Failed to read state file, resuming from 0: {e}")
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        # If resume requested, skip chunks we've already posted
        if args.resume and i <= last_completed:
            continue
        # Build a memory payload that can be used by both fallback and force behaviors
        memory_payload = make_memory_payload(chunk, i)
        # Break out if stop requested before starting a new chunk
        if stop_requested:
            print(f"Stop requested; aborting at chunk {i}")
            break

        try:
            if args.only_memories:
                # Create memory directly without calling /chat
                # memory_payload already created above via make_memory_payload
                try:
                    print(f"Posting /memories (only-memories) for chunk {i}")
                    r = requests.post(args.api.rstrip('/') + '/memories', json=memory_payload, timeout=args.timeout)
                except Exception as e:
                    print("/memories POST failed (only-memories):", e)
                    r = None
            else:
                # Attempt to call the chat endpoint with retry/backoff
                r = None
                max_retries = 3
                attempt = 0
                while attempt < max_retries and r is None and not stop_requested:
                    attempt += 1
                    try:
                        r = post_chat(args.api, args.session, chunk, timeout=args.timeout)
                    except (ReadTimeout, ConnectionError, RequestException) as e:
                        print(f"Call to /chat failed (attempt {attempt}/{max_retries}): {e}")
                        r = None
                        if attempt < max_retries and not stop_requested:
                            wait = 2 ** attempt
                            print(f"Retrying in {wait}s...")
                            # Responsive sleep to allow prompt exit via SIGINT
                            sleep_remaining = wait
                            while sleep_remaining > 0 and not stop_requested:
                                time.sleep(min(0.5, sleep_remaining))
                                sleep_remaining -= 0.5
                # After attempts, fallback to /memories if forced / auto_fallback and chat failed
                # Ensure we have a valid fallback payload if we need to fallback to /memories
                # (memory_payload already created above)
                if r is None and (args.force or args.auto_fallback):
                    print('LLM chat failed - attempting direct POST /memories fallback')
                    # If the server is down, avoid hammering and give a helpful message
                    if not check_api_health(args.api):
                        print('API appears unreachable; skipping fallback POST /memories. If you intended to write directly to Neo4j, run import_direct_neo4j.py or ensure the server is running.')
                        r = None
                    else:
                        try:
                            print(f"Posting fallback /memories for chunk {i} (chunk_index={memory_payload.get('metadata', {}).get('chunk_index')})")
                            r = requests.post(args.api.rstrip('/') + '/memories', json=memory_payload, timeout=args.timeout)
                        except Exception as e:
                            print('Fallback /memories failed:', e)
                            r = None
            # If chat returned a non-success (like 400/500), we may want to fallback depending on flags
            if r is not None and getattr(r, 'status_code', 0) not in (200, 201):
                print(f"/chat returned non-success: {getattr(r,'status_code', None)} {getattr(r,'text', '')}")
                if (args.force or args.auto_fallback):
                    print('Attempting fallback /memories due to chat non-success')
                    if not check_api_health(args.api):
                        print('API appears unreachable; skipping fallback POST /memories')
                        r = None
                    else:
                        try:
                            print(f"Posting fallback /memories for chunk {i} due to chat non-success (chunk_index={memory_payload.get('metadata', {}).get('chunk_index')})")
                            r = requests.post(args.api.rstrip('/') + '/memories', json=memory_payload, timeout=args.timeout)
                        except Exception as e:
                            print('Fallback /memories failed:', e)
                            r = None

            if r is not None and getattr(r, 'status_code', 0) in (200, 201):
                posted += 1
                last_successful = i
                if args.limit and posted >= args.limit:
                    print(f"Reached limit: {args.limit} chunks; aborting")
                    break
                # Update state file as we go so we can resume
                try:
                    with open(state_file, 'w', encoding='utf-8') as sf:
                        json.dump({"last_completed_chunk": i}, sf)
                except Exception:
                    pass
                if posted % args.batch_size == 0:
                    print(f"Posted {posted} chunks; sleeping {args.delay} seconds")
                    time.sleep(args.delay)
            else:
                if r is None:
                    print(f"Failed to post chunk {i}: no response")
                else:
                    print(f"Failed to post chunk {i}: {getattr(r,'status_code', None)} {getattr(r,'text', '')}")
                    if getattr(r, 'status_code', None) == 503:
                        print("Server says Neo4j unavailable. Aborting to avoid silent data loss.")
                    break
            # If the user requested force persistence, create a Memory node via POST /memories
            if args.force:
                # memory_payload already created above via make_memory_payload
                try:
                    r2 = requests.post(args.api.rstrip('/') + '/memories', json=memory_payload, timeout=args.timeout)
                    if getattr(r2, 'status_code', 0) not in (200, 201):
                        print(f"Warning: Failed to force-add memory {i}: {getattr(r2,'status_code', None)} {getattr(r2,'text', '')}")
                except Exception as e:
                    print("Warning: Error forcing memory to Neo4j", e)
        except Exception as e:
            print("Error posting chunk", i, e)
            time.sleep(1)

    # When stopping early, persist the last completed chunk index for resume
    try:
        if stop_requested:
            if 'last_successful' in locals() and last_successful is not None:
                with open(state_file, 'w', encoding='utf-8') as sf:
                    json.dump({"last_completed_chunk": int(last_successful)}, sf)
                    print(f"Saved resume state: last_completed_chunk={last_successful}")
            else:
                print("No completed chunks to save in resume state.")
    except Exception as e:
        print("Failed to write resume state on exit:", e)

    print(f"Import finished. Posted {posted} chunks")

    queries = [q.strip() for q in (args.verify or "Sybil").split(',') if q.strip()]
    for q in queries:
        print(f"Searching for '{q}'...")
        res = search_memory(args.api, q, limit=10)
        print(json.dumps(res, indent=2))

    if args.ask:
        print("Chatting with session to validate memory retrieval")
        resp = post_chat(args.api, args.session, args.ask, timeout=args.timeout)
        if resp.status_code == 200:
            print("Chat response:", json.dumps(resp.json(), indent=2))
        else:
            print("Chat failed:", resp.status_code, resp.text)


if __name__ == '__main__':
    main()
