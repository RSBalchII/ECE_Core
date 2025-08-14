import sys
import os
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

# Pass the relative path to the test file from the project root
test_file_path_relative = os.path.join('tests', 'test_memory_creator.py')

pytest.main([test_file_path_relative])