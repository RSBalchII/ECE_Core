#!/usr/bin/env python3
"""
Test runner for the Injector Agent
"""

import sys
import os
import unittest

# Add the project root directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Add the injector agent directory to the path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "ece", "agents", "tier3", "injector")
)

if __name__ == "__main__":
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), "tests", "injector_agent")
    suite = loader.discover(start_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with error code if tests failed
    sys.exit(not result.wasSuccessful())
