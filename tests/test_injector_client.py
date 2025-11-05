"""
Simple test script to debug the InjectorClient directly
"""

import sys
import os
import asyncio

# Add the archivist agent directory to the path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "ece/agents/tier3/archivist")
)

from archivist_agent import InjectorClient


async def test_injector_client():
    """Test the InjectorClient directly with sample data."""
    # Create an instance of the injector client
    injector_client = InjectorClient()

    # Sample data to inject
    data = {
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
        "relationships": [],
        "summary": "Test data",
    }

    # Try to send data to the injector
    try:
        result = await injector_client.send_data_for_injection(data)
        print("Send data result:", result)
    except Exception as e:
        print(f"Error during send data: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_injector_client())
