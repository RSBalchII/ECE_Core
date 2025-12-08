import requests
import sys

def test_connection():
    print("Testing connection to http://127.0.0.1:8000/health ...")
    try:
        r = requests.get("http://127.0.0.1:8000/health", timeout=2)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Failed: {e}")

    print("\nTesting connection to http://localhost:8000/health ...")
    try:
        r = requests.get("http://localhost:8000/health", timeout=2)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Failed: {e}")

    print("\nTesting POST to http://127.0.0.1:8000/chat/stream ...")
    try:
        r = requests.post("http://127.0.0.1:8000/chat/stream", 
                          json={"session_id": "test", "message": "hi", "stream": True},
                          headers={"Content-Type": "application/json"},
                          timeout=2)
        print(f"Status: {r.status_code}")
        print(f"Headers: {r.headers}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_connection()
