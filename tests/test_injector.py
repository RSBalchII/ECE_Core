"""
Simple test script to debug the Injector agent with detailed error handling
"""

import sys
import os

# Add the injector agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ece/agents/tier3/injector"))

from injector_agent import InjectorAgent


def test_injector():
    """Test the InjectorAgent with sample data."""
    # Create an instance of the injector agent
    injector_agent = InjectorAgent()

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

    # Try to inject the data
    try:
        result = injector_agent.receive_data_for_injection(data)
        print("Injection result:", result)
    except Exception as e:
        print(f"Error during injection: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_injector()
