"""
Packaging verification tests for the External Context Engine.
These tests verify that the packaged application will work correctly.
"""

import unittest
import os
import sys
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from bootstrap import (
    check_required_services,
    load_config,
    check_port,
    check_url,
    check_redis_connection,
    check_neo4j_connection,
)


class TestPackagingVerification(unittest.TestCase):
    """Test cases to verify that the packaging process will work correctly"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)

    def test_config_loading(self):
        """Test that configuration can be loaded from the packaged app."""
        # Create a temporary config file
        config_path = os.path.join(self.test_dir, "config.yaml")
        config_content = """
llm:
  active_provider: llama_cpp
  providers:
    llama_cpp:
      model_path: "./models/test_model.gguf"
      api_base: "http://localhost:8080/v1"
cache:
  redis_url: "redis://localhost:6379"
"""
        with open(config_path, "w") as f:
            f.write(config_content)

        # Test loading the config
        config = load_config(config_path)
        self.assertIsNotNone(config)
        self.assertIn("llm", config)
        self.assertIn("cache", config)

    def test_bootstrap_imports(self):
        """Test that all required modules can be imported in the packaged app."""
        required_modules = [
            "yaml",
            "redis",
            "neo4j",
            "httpx",
            "asyncio",
            "requests",
            "socket",
            "urllib.parse",
        ]

        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError:
                self.fail(
                    f"Module {module_name} cannot be imported in the packaged app"
                )

    @patch("socket.socket")
    def test_port_checking_functionality(self, mock_socket):
        """Test the port checking functionality."""
        # Mock the socket connection to simulate a successful connection
        mock_sock_instance = MagicMock()
        mock_sock_instance.connect_ex.return_value = 0  # Simulate successful connection
        mock_socket.return_value.__enter__.return_value = mock_sock_instance

        result = check_port("localhost", 8080, "Test Service")
        self.assertTrue(result)

    @patch("requests.get")
    def test_url_checking_functionality(self, mock_get):
        """Test the URL checking functionality."""
        # Mock the GET request to simulate a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = check_url("http://localhost:8080", "Test Service")
        self.assertTrue(result)

    def test_spec_file_exists(self):
        """Test that the PyInstaller spec file exists."""
        self.assertTrue(
            os.path.exists("ece_app.spec"), "PyInstaller spec file does not exist"
        )


class MockRedis:
    """Mock Redis class for testing purposes."""

    def __init__(self, *args, **kwargs):
        pass

    def ping(self):
        return True


class MockNeo4jDriver:
    """Mock Neo4j driver for testing purposes."""

    def __init__(self, *args, **kwargs):
        pass

    def session(self, *args, **kwargs):
        return MockSession()


class MockSession:
    """Mock Neo4j session for testing purposes."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self, query):
        return MockResult()


class MockResult:
    """Mock Neo4j result for testing purposes."""

    def single(self):
        return [1]


class TestServiceChecking(unittest.TestCase):
    """Test service checking functionality in the bootstrap module."""

    @patch("bootstrap.redis.Redis")
    def test_redis_connection_check(self, mock_redis_class):
        """Test Redis connection checking."""
        # Mock the Redis class
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        result = check_redis_connection("redis://localhost:6379")
        self.assertTrue(result)

    @patch("bootstrap.GraphDatabase.driver")
    def test_neo4j_connection_check(self, mock_driver_class):
        """Test Neo4j connection checking."""
        # Mock the Neo4j driver
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_session.run.return_value = mock_result
        mock_result.single.return_value = [1]

        mock_driver.session.return_value = mock_session
        mock_driver_class.return_value = mock_driver

        result = check_neo4j_connection("neo4j://localhost:7687", "neo4j", "password")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
