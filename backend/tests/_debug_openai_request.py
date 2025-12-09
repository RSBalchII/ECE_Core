from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

payload = {
    "model": "ece-core",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello."}
    ]
}
headers = {"Authorization": "Bearer testkey"}

resp = client.post('/v1/chat/completions', json=payload, headers=headers)
print('Status:', resp.status_code)
print('Text:', resp.text)
print('JSON:', None if resp.status_code != 200 else resp.json())
