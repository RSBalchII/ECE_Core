"""
Sandbox module for the External Context Engine (ECE).

This module implements secure code execution in isolated Docker containers.
"""

import docker
import uuid
import time
from typing import Dict, Any, Optional


def run_code_in_sandbox(code_string: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Execute code in a secure, isolated Docker container.

    This function creates a temporary container, executes the provided code,
    captures the output, and terminates the container.

    Args:
        code_string (str): The Python code to execute.
        timeout (int): Maximum execution time in seconds.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - stdout (str): Standard output from the execution
            - stderr (str): Standard error from the execution
            - exception (str): Any exception that occurred
            - success (bool): Whether the execution was successful
            - container_id (str): ID of the container used
    """
    client = docker.from_env()

    # Generate a unique container name
    container_name = f"ece-sandbox-{uuid.uuid4().hex[:8]}"

    # Default result structure
    result = {
        "stdout": "",
        "stderr": "",
        "exception": None,
        "success": False,
        "container_id": None,
    }

    try:
        # Create a temporary container with network disabled
        container = client.containers.run(
            "python:3.11-alpine",
            name=container_name,
            command=["python", "-c", code_string],
            detach=True,
            network_disabled=True,  # Critical security feature
            mem_limit="128m",  # Limit memory usage
            cpu_quota=50000,  # Limit CPU usage (50% of one core)
            remove=False,  # Don't auto-remove so we can get logs
        )

        result["container_id"] = container.id

        # Wait for the container to finish with timeout
        exit_code = container.wait(timeout=timeout)

        # Get the logs (stdout and stderr)
        logs = container.logs()
        result["stdout"] = logs.decode("utf-8") if logs else ""

        # Update success status
        result["success"] = exit_code["StatusCode"] == 0

    except docker.errors.ContainerError as e:
        result["exception"] = f"ContainerError: {str(e)}"
        result["stderr"] = e.stderr.decode("utf-8") if e.stderr else ""
    except docker.errors.ImageNotFound:
        result["exception"] = (
            "Docker image not found. Please ensure python:3.11-alpine is available."
        )
    except docker.errors.APIError as e:
        result["exception"] = f"Docker API error: {str(e)}"
    except Exception as e:
        result["exception"] = f"Unexpected error: {str(e)}"
    finally:
        # Always clean up the container
        try:
            # Get the container if it exists
            container = client.containers.get(container_name)
            # Get stderr if we haven't already
            if not result["stderr"]:
                container.reload()
                # For stderr, we might need to check differently
            # Remove the container
            container.remove(force=True)
        except docker.errors.NotFound:
            # Container was already removed
            pass
        except Exception as e:
            result["exception"] = f"Cleanup error: {str(e)}"

    return result


def main():
    """Main entry point for testing the sandbox."""
    print("Sandbox module initialized.")

    # Test with a simple code snippet
    test_code = """
print("Hello from sandbox!")
x = 10
y = 20
print(f"Result: {x} + {y} = {x + y}")
"""

    print("Running test code...")
    result = run_code_in_sandbox(test_code)
    print(f"Success: {result['success']}")
    print(f"Output: {result['stdout']}")
    if result["stderr"]:
        print(f"Errors: {result['stderr']}")
    if result["exception"]:
        print(f"Exception: {result['exception']}")


if __name__ == "__main__":
    main()
