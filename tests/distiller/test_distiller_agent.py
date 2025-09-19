import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from ece.agents.tier3.distiller.distiller_agent import DistillerAgent
from ece.components.context_cache.cache_manager import CacheManager

class TestDistillerAgent(unittest.TestCase):
    pass

if __name__ == '__main__':
    unittest.main()