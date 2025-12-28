#!/usr/bin/env python3
"""
Sovereign Terminal Client (The Shell)
Implements the native client for the Ghost & Shell architecture.
Communicates with the headless Ghost engine via HTTP API.
"""

import os
import sys
import json
import requests
import argparse
from pathlib import Path

class SovereignClient:
    def __init__(self, base_url="http://localhost:8080", token=None):
        self.base_url = base_url
        self.token = token or os.getenv("BRIDGE_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def chat_completion(self, messages, stream=False):
        """Send chat completion request to the Ghost engine."""
        url = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "model": "default",
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with Ghost engine: {e}")
            return None
    
    def execute_shell_command(self, command):
        """Execute a shell command via the Neural Shell Protocol."""
        url = f"{self.base_url}/v1/shell/exec"
        
        payload = {
            "cmd": command
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error executing shell command: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Sovereign Terminal Client (The Shell)")
    parser.add_argument("prompt", nargs="*", help="The prompt to send to the Ghost engine")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Base URL for the Ghost engine")
    parser.add_argument("--token", help="Authentication token for the bridge")
    parser.add_argument("--shell", "-s", action="store_true", help="Execute as shell command via Neural Shell Protocol")
    
    args = parser.parse_args()
    
    client = SovereignClient(base_url=args.base_url, token=args.token)
    
    if not args.prompt:
        # Interactive mode
        print("Sovereign Terminal Client (The Shell)")
        print("Type 'exit' or 'quit' to exit")
        print(f"Connected to Ghost engine at {args.base_url}")
        print("")
        
        while True:
            try:
                user_input = input("sov> ").strip()
                if user_input.lower() in ['exit', 'quit', 'q']:
                    break
                
                if args.shell:
                    result = client.execute_shell_command(user_input)
                    if result:
                        print(json.dumps(result, indent=2))
                else:
                    messages = [{"role": "user", "content": user_input}]
                    response = client.chat_completion(messages)
                    if response:
                        choice = response.get("choices", [{}])[0]
                        message = choice.get("message", {})
                        content = message.get("content", "")
                        print(content)
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
    else:
        # Command mode
        prompt = " ".join(args.prompt)
        
        if args.shell:
            result = client.execute_shell_command(prompt)
            if result:
                print(json.dumps(result, indent=2))
        else:
            messages = [{"role": "user", "content": prompt}]
            response = client.chat_completion(messages)
            if response:
                choice = response.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "")
                print(content)

if __name__ == "__main__":
    main()