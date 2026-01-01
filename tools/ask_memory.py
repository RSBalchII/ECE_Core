#!/usr/bin/env python3
"""
Anchor Memory Retriever
Usage: python ask_memory.py "What did I work on last week?"
"""
import sys
import requests
import argparse
import json

# Configuration
BRIDGE_URL = "http://localhost:8000"

def search_memory(query):
    print(f"⚓ Querying Anchor Memory for: '{query}'...")
    try:
        response = requests.post(
            f"{BRIDGE_URL}/v1/memory/search",
            json={"query": query},
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return data.get('result', '')
            else:
                print(f"❌ Error from Engine: {data.get('error')}")
        elif response.status_code == 503:
            print(f"❌ Service unavailable: Ghost Engine not connected. Is chat.html open?")
        elif response.status_code == 400:
            print(f"❌ Bad request: {response.json().get('error', 'Invalid query')}")
        elif response.status_code == 504:
            print(f"❌ Gateway timeout: Search took too long")
        else:
            print(f"❌ Bridge Error ({response.status_code}): {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to Anchor Bridge at {BRIDGE_URL}")
        print("   Is 'start-anchor.bat' running?")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    return None

def main():
    parser = argparse.ArgumentParser(description="Query your local Anchor Memory system.")
    parser.add_argument("query", nargs="+", help="The question or topic to search for.")
    args = parser.parse_args()
    
    full_query = " ".join(args.query)
    
    context = search_memory(full_query)
    
    if context:
        print("\n" + "="*60)
        print("📋 COPY THE TEXT BELOW TO WEBLLM CHAT")
        print("="*60 + "\n")
        print(context)
        print("\n" + "="*60)
        
        # Optional: Auto-copy to clipboard if user has pyperclip
        try:
            import pyperclip
            pyperclip.copy(context)
            print("✅ Copied to clipboard automatically!")
        except ImportError:
            print("(Tip: Install 'pyperclip' to auto-copy: pip install pyperclip)")
    else:
        print("\n❌ Failed to retrieve memory context.")
        print("Make sure:")
        print("1. Anchor Core is running (start-anchor.bat)")
        print("2. The chat.html page is open and connected")
        print("3. The database has been initialized")

if __name__ == "__main__":
    main()