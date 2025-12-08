#!/usr/bin/env python
"""Dump session context values from Redis (list keys matching session:*:context).
"""
import argparse
import json
import asyncio

import os
DEFAULT_REDIS = os.getenv('REDIS_URL', os.getenv('REDIS_URL_OVERRIDE', os.getenv('REDIS_URL', 'redis://localhost:6379')))

try:
    import redis.asyncio as redis
except Exception as e:
    print("redis.asyncio not installed (are you in the ECE_Core virtual env?). Install redis package via pip.")
    raise

async def main(host: str = None, port: int = None, url: str = None):
    # Determine redis URL (prefer explicit --url, else fall back to DEFAULT_REDIS)
    redis_url = url or DEFAULT_REDIS
    r = redis.from_url(redis_url, decode_responses=True)
    try:
        ping = r.ping()
        if hasattr(ping, '__await__'):
            await ping
        print(f"Connected to Redis at {redis_url}")
    except Exception as e:
        print(f"Failed to connect to Redis at {redis_url}: {e}")
        return
    try:
        # Use scan to find session keys
        cursor = 0
        found = []
        while True:
            cursor, keys = await r.scan(cursor=cursor, match="session:*:context", count=100)
            for k in keys:
                val = await r.get(k)
                found.append((k, val))
            if cursor == 0:
                break
        if not found:
            print("No session contexts found in Redis (session:*:context)")
            return
        print(f"Found {len(found)} session context(s):\n")
        for k, v in found:
            print(f"--- {k} ---")
            if not v:
                print("(empty)")
                continue
            summary = v[:2000]
            if len(v) > 2000:
                print(summary + "\n... (truncated) ...")
            else:
                print(summary)
            # We'll avoid printing full extremely long contexts to the terminal
            print('\n')
    finally:
        try:
            await r.close()
        except Exception:
            pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--redis-url', '-u', type=str, default=None)
    args = parser.parse_args()
    asyncio.run(main(url=args.redis_url))
