#!/usr/bin/env python3
import httpx
api='http://127.0.0.1:8081'
try:
    r = httpx.get(f'{api}/v1/models', timeout=10.0)
    print('GET /v1/models status:', r.status_code)
    print('Body:', r.text[:2000])
except Exception as e:
    print('GET models failed:', e)

# Try embeddings with a guessed model name
try:
    payload = {"model": "embeddinggemma-300m.Q8_0.gguf", "input": ["hello world"]}
    r = httpx.post(f'{api}/v1/embeddings', json=payload, timeout=30.0)
    print('POST /v1/embeddings status:', r.status_code)
    print('Body:', r.text[:2000])
except Exception as e:
    print('POST embeddings failed:', e)
