import requests
import json
import sys

def test_chat():
    url = "http://localhost:8000/chat/"
    payload = {
        "session_id": "debug-session",
        "message": "Hello from debug script",
        "system_prompt": "You are a helpful assistant."
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"Sending POST to {url}...")
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {response.headers}")
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(response.text)
            return

        data = response.json()
        print("Response JSON:")
        print(json.dumps(data, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat()
