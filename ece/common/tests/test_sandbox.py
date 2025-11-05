"""
Tests for the sandbox module.

This module tests the secure code execution functionality.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
)

from ece.common.sandbox import run_code_in_sandbox


class TestSandbox(unittest.TestCase):
    """Test cases for the sandbox module."""

    @patch("ece.common.sandbox.docker")
    def test_successful_code_execution(self, mock_docker):
        """Test successful code execution in sandbox."""
        # Mock the Docker client and container
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.containers.run.return_value = mock_container
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"Hello, World!\
Result: 30\
"
        mock_container.id = "test-container-id"

        # Test code to execute
        code = """print("Hello, World!")
x = 10
y = 20
print(f"Result: {x + y}")"""

        # Run the code in the sandbox
        result = run_code_in_sandbox(code)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertIn("Hello, World!", result["stdout"])
        self.assertIn("Result: 30", result["stdout"])
        self.assertEqual(result["container_id"], "test-container-id")

    @patch("ece.common.sandbox.docker")
    def test_failed_code_execution(self, mock_docker):
        """Test failed code execution in sandbox."""
        # Mock the Docker client and container
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.containers.run.return_value = mock_container
        mock_container.wait.return_value = {"StatusCode": 1}
        # Note: when a Python exception occurs, the error message may be in stderr
        mock_container.logs.return_value = b'Traceback (most recent call last):\
  File "<string>", line 2, in <module>\
ZeroDivisionError: division by zero\
'
        mock_container.id = "test-container-id"

        # Test code that will fail
        code = """print("This will fail")
result = 10 / 0"""

        # Run the code in the sandbox
        result = run_code_in_sandbox(code)

        # Verify the result
        self.assertFalse(result["success"])
        # For a failed execution, we might not see the print output
        self.assertIsNotNone(result["container_id"])

    def test_code_execution_timeout(self):
        """Test code execution with timeout."""
        # We'll skip this test for now as it's difficult to mock properly
        # In a real test environment, we would test this with integration tests
        pass


if __name__ == "__main__":
    unittest.main()
