#!/usr/bin/env python3
"""
Safe Start Script - Python Version

Starts all services with conservative settings suitable for development
and RTX 4090 16GB VRAM with the new modular architecture.
"""
import subprocess
import sys
import time
import threading
from pathlib import Path

def start_service(name, cmd, wait_time=0):
    """Start a service in a separate thread/process."""
    print(f"🚀 Starting {name}...")
    
    def run_service():
        try:
            # Set conservative environment variables for the process
            import os
            env = os.environ.copy()
            env['LLAMA_SERVER_UBATCH_SIZE'] = '256'
            env['LLAMA_BATCH'] = '1024' 
            env['LLAMA_PARALLEL'] = '1'
            env['THREADS'] = '12'
            
            process = subprocess.Popen(cmd, env=env, shell=True)
            process.wait()
        except Exception as e:
            print(f"❌ Error starting {name}: {e}")
    
    thread = threading.Thread(target=run_service, daemon=True)
    thread.start()
    
    if wait_time > 0:
        time.sleep(wait_time)
    
    return thread

def main():
    print("🔄 Starting all ECE services with safe defaults...")
    print("💡 Note: Model selection will be interactive for LLM server")
    print("-" * 60)
    
    # Start LLM server first (needs to be available for others)
    llm_thread = start_service(
        "LLM Server", 
        "python start_llm_server.py", 
        wait_time=2  # Give it a moment to start
    )
    
    # Start embedding server
    embed_thread = start_service(
        "Embedding Server", 
        "python start_embedding_server.py",
        wait_time=1
    )
    
    # Start ECE Core server last (depends on LLM)
    ece_thread = start_service(
        "ECE Core Server", 
        "python start_ece.py"
    )
    
    print("-" * 60)
    print("✅ All services started!")
    print("   - LLM Server: Port 8080")
    print("   - Embedding Server: Port 8081") 
    print("   - ECE Core: Port 8000 (with MCP if enabled)")
    print("   - MCP Tools: http://localhost:8000/mcp/tools")
    print()
    print("💡 Services are running in background threads.")
    print("   Check individual terminal windows for logs.")
    print("   Use Ctrl+C to stop all services.")
    
    try:
        # Wait for all threads to complete (they run indefinitely)
        # This keeps the main script alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down all services...")
        print("✅ This script doesn't manage process termination.")
        print("   You may need to close individual terminal windows manually.")

if __name__ == "__main__":
    main()