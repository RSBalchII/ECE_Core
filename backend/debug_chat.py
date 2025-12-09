import requests
import json
import sys

def test_chat():
    url = "http://localhost:8000/chat/stream"
    payload = {
        "session_id": "debug-session",
        "message": "Hello from debug script",
        "stream": True
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"Sending POST to {url}...")
    try:
        with requests.post(url, json=payload, headers=headers, stream=True) as response:
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {response.headers}")
            
            if response.status_code == 403:
                print("Request Forbidden!")
                print(response.text)
                return

            print("Response stream:")
            for line in response.iter_lines():
                if line:
                    print(line.decode('utf-8'))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat()
