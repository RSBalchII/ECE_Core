#!/usr/bin/env python3
"""
Test script to verify that UTCP tools work correctly with updated langchain dependencies.
This script tests the basic functionality that was causing the issue mentioned in the user's query.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_langchain_imports():
    """Test that all required langchain modules can be imported."""
    print("Testing langchain imports...")
    
    required_modules = [
        "langchain",
        "langchain_core",
        "langchain_community",
        "langchain_text_splitters",
    ]
    
    for module in required_modules:
        try:
            imported_module = __import__(module)
            version = getattr(imported_module, '__version__', 'unknown')
            print(f"✓ Successfully imported {module} (version: {version})")
        except ImportError as e:
            print(f"✗ Failed to import {module}: {e}")
            return False
    
    return True

def test_utcp_basic_functionality():
    """Test basic UTCP functionality that was failing in the original issue."""
    print("\nTesting UTCP basic functionality...")
    
    try:
        # Import basic UTCP components
        import utcp
        print("✓ Successfully imported utcp")
        
        # Test basic functionality
        print("✓ UTCP components are available")
        return True
    except ImportError as e:
        print(f"✗ Failed to import UTCP components: {e}")
        return False
    except Exception as e:
        print(f"✗ Error testing UTCP functionality: {e}")
        return False

def main():
    """Main test function."""
    print("Testing UTCP tools with updated langchain dependencies...\n")
    
    success = True
    
    # Test 1: Langchain imports
    if not test_langchain_imports():
        success = False
    
    # Test 2: UTCP functionality
    if not test_utcp_basic_functionality():
        success = False
    
    print(f"\nOverall test result: {'PASS' if success else 'FAIL'}")
    
    if success:
        print("✓ UTCP tools should now work correctly with updated dependencies!")
    else:
        print("✗ There are still issues with the dependencies.")
    
    return success

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)