#!/usr/bin/env python3
"""
Anchor Terminal - Native Shell Interface for Sovereign Context Bridge

This script provides a native Python terminal interface that connects to the
WebGPU bridge and provides direct access to system resources while maintaining
the neural shell protocol.
"""

import os
import sys
import json
import requests
import subprocess
import platform
import argparse
from pathlib import Path
from datetime import datetime


class AnchorTerminal:
    def __init__(self, bridge_url="http://localhost:8080", token="sovereign-secret"):
        self.bridge_url = bridge_url
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.running = True
        self.history = []
        
    def execute_shell_command(self, cmd):
        """Execute a shell command via the bridge"""
        try:
            payload = {"cmd": cmd}
            response = requests.post(
                f"{self.bridge_url}/v1/shell/exec",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            return response.json()
        except Exception as e:
            return {"error": str(e), "stdout": "", "stderr": str(e), "code": -1}

    def execute_local_command(self, cmd):
        """Execute a command locally on the host system"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "code": result.returncode,
                "cmd": cmd
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out (30s limit)", "stdout": "", "stderr": "", "code": -1}
        except Exception as e:
            return {"error": str(e), "stdout": "", "stderr": str(e), "code": -1}

    def display_response(self, response):
        """Display the command response in a formatted way"""
        if "error" in response and response["error"]:
            print(f"❌ Error: {response['error']}")
        else:
            if response.get("stdout"):
                print(response["stdout"], end="")
            if response.get("stderr"):
                print(f"⚠️  stderr: {response['stderr']}", end="")
            if "code" in response and response["code"] != 0:
                print(f"🔄 Exit code: {response['code']}")

    def help_menu(self):
        """Display help information"""
        print("\n" + "="*60)
        print("ANCHOR TERMINAL - NEURAL SHELL PROTOCOL")
        print("="*60)
        print("Commands:")
        print("  !<cmd>     - Execute via bridge (remote execution)")
        print("  <cmd>      - Execute locally on host")
        print("  !help      - Show bridge commands")
        print("  history    - Show command history")
        print("  clear      - Clear screen")
        print("  exit       - Exit the terminal")
        print("  !status    - Check bridge status")
        print("  !memories  - Search memories (if available)")
        print("="*60 + "\n")

    def check_bridge_status(self):
        """Check if the bridge is accessible"""
        try:
            response = requests.get(f"{self.bridge_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Bridge connected: {self.bridge_url}")
                return True
            else:
                print(f"❌ Bridge error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Bridge unreachable: {e}")
            return False

    def search_memories(self, query):
        """Search memories via the bridge"""
        try:
            payload = {"query": query}
            response = requests.post(
                f"{self.bridge_url}/memories/search",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            if response.status_code == 200:
                results = response.json()
                if results:
                    print(f"🧠 Found {len(results)} memory matches:")
                    for i, memory in enumerate(results, 1):
                        print(f"  {i}. {memory}")
                else:
                    print("🧠 No memories found for query.")
            else:
                print(f"❌ Memory search failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Memory search error: {e}")

    def run(self):
        """Main terminal loop"""
        print(f"⚓ ANCHOR TERMINAL v1.0")
        print(f"🔗 Connected to: {self.bridge_url}")
        print(f"🖥️  Host: {platform.system()} {platform.release()}")
        print(f"Type 'help' for available commands or 'exit' to quit.\n")
        
        # Check bridge status
        self.check_bridge_status()
        print()
        
        while self.running:
            try:
                # Get user input
                user_input = input(f"anchor@{platform.node()}$ ").strip()
                
                if not user_input:
                    continue
                    
                # Add to history
                self.history.append({"timestamp": datetime.now().isoformat(), "command": user_input})
                
                # Process commands
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 Anchor terminal closing...")
                    self.running = False
                    
                elif user_input.lower() == 'help':
                    self.help_menu()
                    
                elif user_input.lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    
                elif user_input.lower() == 'history':
                    print("\nCommand History:")
                    for i, entry in enumerate(self.history[-10:], 1):  # Show last 10
                        print(f"  {i:2d}. {entry['command']}")
                    print()
                    
                elif user_input.startswith('!status'):
                    self.check_bridge_status()
                    
                elif user_input.startswith('!memories '):
                    query = user_input[10:].strip()
                    if query:
                        self.search_memories(query)
                    else:
                        print("Usage: !memories <search_query>")
                        
                elif user_input.startswith('!'):
                    # Execute via bridge
                    cmd = user_input[1:].strip()
                    if cmd:
                        print(f"📡 Executing on bridge: {cmd}")
                        response = self.execute_shell_command(cmd)
                        self.display_response(response)
                    else:
                        print("Usage: !<command>")
                        
                else:
                    # Execute locally
                    print(f"💻 Executing locally: {user_input}")
                    response = self.execute_local_command(user_input)
                    self.display_response(response)
                    
            except KeyboardInterrupt:
                print("\n⚠️  Use 'exit' to quit the terminal.")
            except EOFError:
                print("\n👋 Anchor terminal closing...")
                self.running = False


def main():
    parser = argparse.ArgumentParser(description="Anchor Terminal - Native Shell for Sovereign Context Bridge")
    parser.add_argument("--bridge-url", default="http://localhost:8080", 
                       help="URL of the WebGPU bridge (default: http://localhost:8080)")
    parser.add_argument("--token", default="sovereign-secret", 
                       help="Authentication token for the bridge")
    
    args = parser.parse_args()
    
    terminal = AnchorTerminal(bridge_url=args.bridge_url, token=args.token)
    terminal.run()


if __name__ == "__main__":
    main()