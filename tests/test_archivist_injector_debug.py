#!/usr/bin/env python3
"""
Script to test the Archivist and Injector agents together to replicate the "'str' object is not callable" error.
"""

import asyncio
import httpx
import time
import sys
import os

# Add the project root directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


async def test_archivist_injector_integration():
    """Test the integration between Archivist and Injector agents."""

    # Wait a bit for the agents to start
    print("Waiting for agents to start...")
    time.sleep(2)

    # Test data to send to the Archivist
    test_data = {
        "entities": [
            {
                "id": "test_entity_1",
                "type": "Concept",
                "properties": {
                    "name": "Test Concept",
                    "description": "A test concept for debugging",
                },
            }
        ],
        "relationships": [
            {
                "start_id": "test_entity_1",
                "start_type": "Concept",
                "end_id": "test_entity_2",
                "end_type": "Concept",
                "type": "RELATED_TO",
                "properties": {"strength": 0.8},
            }
        ],
        "summary": "Test data for debugging the 'str' object is not callable error",
    }

    # Send request to Archivist
    print("Sending request to Archivist...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8003/internal/data_to_archive",
                json=test_data,
                timeout=30.0,
            )
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {response.headers}")
            print(f"Response text: {response.text}")

            if response.status_code == 200:
                result = response.json()
                print(f"Success response: {result}")
            else:
                print(f"Error response: {response.text}")
    except Exception as e:
        print(f"Error calling Archivist: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_archivist_injector_integration())
