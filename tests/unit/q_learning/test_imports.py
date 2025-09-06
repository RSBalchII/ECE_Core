"""
Simple test to verify Q-learning module imports and instantiation
"""
import pytest
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

def test_import_q_learning_agent():
    """Test that the QLearningGraphAgent can be imported"""
    try:
        from src.external_context_engine.memory_management.q_learning.q_learning_agent import QLearningGraphAgent
        assert QLearningGraphAgent is not None
    except ImportError as e:
        pytest.fail(f"Failed to import QLearningGraphAgent: {e}")

def test_import_memory_path():
    """Test that the MemoryPath model can be imported"""
    try:
        from src.external_context_engine.memory_management.models.memory_path import MemoryPath
        assert MemoryPath is not None
    except ImportError as e:
        pytest.fail(f"Failed to import MemoryPath: {e}")

if __name__ == "__main__":
    test_import_q_learning_agent()
    test_import_memory_path()
    print("All import tests passed!")