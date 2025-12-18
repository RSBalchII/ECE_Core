import argparse
import requests
import sys
import os

def ingest(content, source_type="text", adapter="eyes-cli"):
    url = "http://localhost:8000/archivist/ingest"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": "ece-secret-key" 
    }
    payload = {
        "content": content,
        "type": source_type,
        "adapter": adapter
    }
    
    print(f"Sending to {url}...")
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"✅ Success: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Details: {e.response.text}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Sovereign Eyes - Ingest content into ECE Memory")
    parser.add_argument("input", help="File path or text content to ingest")
    parser.add_argument("--type", default="text", help="Source type (text, web_page, etc.)")
    parser.add_argument("--adapter", default="eyes-cli", help="Adapter name")
    
    args = parser.parse_args()
    
    content = args.input
    
    # Check if input is a file
    if os.path.exists(args.input):
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"📖 Read content from file: {args.input}")
        except Exception as e:
            print(f"⚠️ Could not read file '{args.input}', treating as raw text.")
            
    ingest(content, args.type, args.adapter)

if __name__ == "__main__":
    main()
