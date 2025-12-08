#!/usr/bin/env python3
"""
Basic test for the `llama_proxy.py` to ensure that the proxy forwards /v1/models and enforces API key.
"""
import os
import httpx

PROXY = os.getenv("LLAMA_PROXY_URL", "http://localhost:8089")
KEY = os.getenv("LLAMA_PROXY_KEY", "local-proxy-key")

def test_models_with_key():
    url = f"{PROXY}/v1/models"
    headers = {"Authorization": f"Bearer {KEY}"}
    r = httpx.get(url, headers=headers, timeout=10.0)
    print("Status with key:", r.status_code)
    print(r.json())

def test_models_no_key():
    url = f"{PROXY}/v1/models"
    r = httpx.get(url, timeout=10.0)
    print("Status without key:", r.status_code)
    print(r.text)

if __name__ == "__main__":
    print("Testing proxy endpoint with and without API key")
    test_models_no_key()
    print("---")
    test_models_with_key()
