#!/usr/bin/env python
"""Dump session context from running ECE_Core server.
Usage: python dump_context.py --session anchor-session --host http://127.0.0.1:8000
"""
import argparse
import json

try:
    import httpx
except Exception:
    import urllib.request as ureq
    import urllib.parse as uparse
    def fetch(url):
        with ureq.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
else:
    def fetch(url):
        r = httpx.get(url, timeout=10.0)
        r.raise_for_status()
        return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', '-s', type=str, default='anchor-session', help='session id to query')
    parser.add_argument('--host', '-H', type=str, default='http://127.0.0.1:8000', help='ECE_Core server base URL')
    args = parser.parse_args()

    url = args.host.rstrip('/') + f'/context/{args.session}'
    try:
        data = fetch(url)
    except Exception as e:
        print(f"Failed to fetch context for session '{args.session}' from {args.host} - {e}")
        return

    print(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
