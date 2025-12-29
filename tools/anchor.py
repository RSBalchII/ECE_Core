import sys
import os
import requests
import argparse
import json

class AnchorTerminal:
    def __init__(self, bridge_url="http://localhost:8080"):
        self.bridge_url = bridge_url
        self.headers = {"Authorization": "Bearer sovereign-secret"}

    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"⚓ ANCHOR SHELL v1.0")
        print(f"   Connected to Ghost at {self.bridge_url}")
        print("   Type 'exit' to quit. Use English to generate commands.")
        print("="*60)

        while True:
            try:
                user_input = input(f"\n⚓ {os.getcwd()} > ").strip()
                if not user_input: continue
                if user_input.lower() in ['exit', 'quit']: break
                if user_input.lower() == 'clear':
                    os.system('cls')
                    continue

                # Assume English input intended for Ghost
                print("   👻 Thinking...", end="\r")
                try:
                    res = requests.post(
                        f"{self.bridge_url}/v1/shell/exec",
                        headers=self.headers,
                        json={"prompt": user_input},
                        timeout=30
                    )
                    print(" " * 20, end="\r")

                    if res.status_code == 200:
                        data = res.json()
                        if "command" in data:
                            print(f"   💡 {data.get('explanation', 'Suggested command:')}")
                            print(f"   👉 {data['command']}")

                            confirm = input("\n   Execute? [Y/n] ")
                            if confirm.lower() != 'n':
                                print(f"   [Executing]...")
                                os.system(data['command'])
                        elif "error" in data:
                            print(f"   ❌ Ghost Error: {data['error']}")
                    else:
                        print(f"   ❌ Bridge Error: {res.status_code}")

                except Exception as e:
                    print(f"   ❌ Connection Error: {e}")

            except KeyboardInterrupt:
                print("\n")
                continue

if __name__ == "__main__":
    AnchorTerminal().run()
