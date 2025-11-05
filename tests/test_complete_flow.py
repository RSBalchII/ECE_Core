"""
Simple test script to debug the complete flow
"""

import sys
import os
import asyncio

# Add the archivist agent directory to the path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "ece/agents/tier3/archivist")
)

from archivist_agent import InjectorClient


async def test_complete_flow():
    """Test the complete flow with sample data."""
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

        # Process the result in the same way as the receive_distiller_data function
        if result.get("success"):
            print("Data successfully sent to Injector")
            response = {
                "status": "processed",
                "message": "Data sent to Injector successfully",
            }
        else:
            error_msg = result.get("error", "Unknown error")
            print(f"error_msg: {error_msg}, type: {type(error_msg)}")
            # Check if error_msg is callable (it shouldn't be)
            if callable(error_msg):
                print("error_msg is callable, which is unexpected")
                raise Exception("error_msg is callable")
            print(f"Failed to send data to Injector: {error_msg}")
            raise Exception(f"Failed to inject data: {error_msg}")

        print("Response:", response)
    except Exception as e:
        print(f"Error during complete flow: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
