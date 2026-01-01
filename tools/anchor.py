import requests
import sys
import json
import os
from datetime import datetime

# Configuration
BRIDGE_URL = "http://localhost:8000"
CONTEXT_DIR = "../context/sessions"  # Path relative to tools/

def ensure_session_file():
    """Creates a daily session file if it doesn't exist"""
    if not os.path.exists(CONTEXT_DIR):
        os.makedirs(CONTEXT_DIR)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{CONTEXT_DIR}/chat_{date_str}.md"

    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# Chat Session: {date_str}\n\n")

    return filename

def append_to_log(role, text):
    """Writes the message to the daily markdown file"""
    filename = ensure_session_file()
    timestamp = datetime.now().strftime("%H:%M:%S")

    with open(filename, "a", encoding="utf-8") as f:
        # Format as Markdown
        f.write(f"### {role.upper()} [{timestamp}]\n")
        f.write(f"{text}\n\n")

def check_connection():
    try:
        requests.get(f"{BRIDGE_URL}/health", timeout=1)
        return True
    except:
        return False

def chat_loop():
    print("\n⚓ Anchor Terminal (Chat Mode)")
    print("--------------------------------")
    print(f"📁 Session Log: {os.path.abspath(CONTEXT_DIR)}")
    print("Connecting to Ghost Engine...")

    if not check_connection():
        print(f"❌ Could not connect to {BRIDGE_URL}")
        print("   -> Run 'start-anchor.bat' first.")
        return

    # Conversation History
    history = [
        {"role": "system", "content": "You are Anchor, a helpful AI assistant running locally."}
    ]

    print("✅ Connected. Type 'exit' to quit, 'clear' to reset.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input: continue

            if user_input.lower() in ['exit', 'quit']:
                print("👋 Disconnecting.")
                break

            if user_input.lower() == 'clear':
                history = [history[0]]
                print("--- Context Cleared ---")
                continue

            # 1. Update History & Log
            history.append({"role": "user", "content": user_input})
            append_to_log("user", user_input)

            print("Anchor: ", end="", flush=True)

            # 2. Send to Bridge
            try:
                response = requests.post(
                    f"{BRIDGE_URL}/v1/chat/completions",
                    json={
                        "messages": history,
                        "stream": True
                    },
                    stream=True,
                    timeout=120
                )

                if response.status_code == 200:
                    ai_text = ""
                    for line in response.iter_lines(decode_unicode=True):
                        if line and line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]": break
                            try:
                                chunk = json.loads(data_str)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    content = chunk['choices'][0].get('delta', {}).get('content', '')
                                    if content:
                                        print(content, end="", flush=True)
                                        ai_text += content
                            except: continue

                    print("\n")
                    # 3. Update History & Log Assistant Response
                    history.append({"role": "assistant", "content": ai_text})
                    append_to_log("assistant", ai_text)

                else:
                    print(f"❌ Error {response.status_code}: {response.text}")

            except Exception as e:
                print(f"❌ Request Failed: {e}")

        except KeyboardInterrupt:
            print("\nInterrupted.")
            break

if __name__ == "__main__":
    chat_loop()