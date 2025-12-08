#!/usr/bin/env python3
"""
scripts/test_anchor_connectivity.py

Verify that Anchor can reach ECE_Core and print human-friendly errors if not.

Usage:
    python scripts/test_anchor_connectivity.py [--url http://127.0.0.1:8000]

"""
import argparse
import asyncio
import httpx
import os


async def main(url: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            print(f"Checking health endpoint: {url}/health")
            r = await client.get(f"{url}/health")
            print(f"Health: {r.status_code} - {r.text[:200]}")
        except Exception as e:
            print(f"[ERROR] Could not reach {url}/health: {e}")
            return 1

        try:
            print(f"Posting test chat to {url}/chat")
            payload = {"session_id": "test", "message": "Hello from connectivity test"}
            r = await client.post(f"{url}/chat", json=payload)
            print(f"Chat POST: {r.status_code} - {r.text[:200]}")
        except Exception as e:
            print(f"[ERROR] Chat POST failed: {e}")
            return 1

    print("Connectivity OK")
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--url', '-u', default=os.getenv('ECE_URL', 'http://127.0.0.1:8000'))
    args = p.parse_args()
    asyncio.run(main(args.url))
