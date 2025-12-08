#!/usr/bin/env python3
"""
Test script to verify MCP server and Cline integration
"""
import asyncio
import httpx
import json

async def test_mcp_server():
    """Test that the MCP server is working correctly"""
    base_url = "http://localhost:8000"
    
    print("Testing MCP Server at", base_url)
    print("-" * 50)
    
    # Test 1: Health check
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("✅ Health check: OK")
                print("   Response:", response.json())
            else:
                print("❌ Health check: Failed")
                print("   Status:", response.status_code)
    except Exception as e:
        print(f"❌ Health check: Connection failed - {e}")
        return False
    
    # Test 2: MCP tools endpoint
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/mcp/tools")
            if response.status_code == 200:
                tools_data = response.json()
                print("✅ MCP Tools endpoint: OK")
                print(f"   Available tools: {len(tools_data.get('tools', []))}")
                for tool in tools_data.get('tools', []):
                    print(f"   - {tool.get('name')}: {tool.get('description', 'No description')}")
            else:
                print("❌ MCP Tools endpoint: Failed")
                print("   Status:", response.status_code)
    except Exception as e:
        print(f"❌ MCP Tools endpoint: Connection failed - {e}")
    
    # Test 3: Check if LLM server is running
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"http://localhost:8080/v1/models")
            if response.status_code == 200:
                print("✅ LLM Server (port 8080): OK")
                models = response.json().get('data', [])
                print(f"   Available models: {len(models)}")
                for model in models:
                    print(f"   - {model.get('id', 'Unknown')}")
            else:
                print("❌ LLM Server (port 8080): Failed")
    except Exception as e:
        print(f"❌ LLM Server (port 8080): Connection failed - {e}")
    
    print("-" * 50)
    print("Test complete. If all services are running, Cline should be able to connect.")
    return True

if __name__ == "__main__":
    asyncio.run(test_mcp_server())