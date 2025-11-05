"""
Simple test script to simulate the error condition
"""

import sys
import os

# Add the archivist agent directory to the path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "ece/agents/tier3/archivist")
)


def test_string_callable():
    """Test if we can reproduce the 'str' object is not callable error."""
    # Simulate a result from the injector client
    result = {
        "success": False,
        "error": "Connection error: All connection attempts failed",
    }

    # Process the result in the same way as the receive_distiller_data function
    if result.get("success"):
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

        # Try to reproduce the error by accidentally calling error_msg as a function
        try:
            # This would cause the "'str' object is not callable" error
            result = error_msg()
            print("This should not happen")
        except TypeError as e:
            print(f"Caught expected error: {e}")

        print(f"Failed to send data to Injector: {error_msg}")
        raise Exception(f"Failed to inject data: {error_msg}")

    print("Response:", response)


if __name__ == "__main__":
    try:
        test_string_callable()
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
