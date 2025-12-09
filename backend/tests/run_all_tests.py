"""
ECE_Core Master Test Runner

Runs all test suites and provides comprehensive coverage report.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Tuple
import importlib.util

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def run_test_suite(name: str, module_path: Path) -> Tuple[str, bool, int, int]:
    """Run a test suite and return results."""
    try:
        # Load module from file path
        spec = importlib.util.spec_from_file_location("test_module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Run the test
        success = await module.run_all_tests()
        
        return (name, success, 1, 1 if success else 0)
        
    except Exception as e:
        print(f"\n[FAIL] {name} suite crashed: {e}")
        import traceback
        traceback.print_exc()
        return (name, False, 1, 0)


async def main():
    """Run all test suites."""
    print("\n" + "="*80)
    print("=" + " "*78 + "=")
    print("=" + "  ECE_Core Comprehensive Test Suite".center(78) + "=")
    print("=" + " "*78 + "=")
    print("="*80 + "\n")
    
    # Get tests directory
    tests_dir = Path(__file__).parent
    
    # Define test suites with file paths
    suites = [
        ("Core: Memory System", tests_dir / "test_core_memory.py"),
        ("Core: LLM Client", tests_dir / "test_core_llm.py"),
    ]

    # Conditionally include the UTCP integration suite if UTCP plugin is available
    try:
        import importlib
        utcp_spec = importlib.util.find_spec('src.utils.utcp_filesystem')
        if utcp_spec is not None:
            suites.append(("UTCP: Client Integration", tests_dir / "test_utcp_client.py"))
    except Exception:
        # Skip UTCP test if we cannot import utcp modules
        pass
    
    results = []
    for name, module_path in suites:
        print(f"\n{'='*80}")
        print(f"Running: {name}")
        print(f"{'='*80}")
        
        result = await run_test_suite(name, module_path)
        results.append(result)
    
    # Overall summary
    print("\n\n" + "="*80)
    print("=" + " "*78 + "=")
    print("=" + "  FINAL TEST SUMMARY".center(78) + "=")
    print("=" + " "*78 + "=")
    print("="*80 + "\n")
    
    total_suites = len(results)
    passed_suites = sum(1 for _, success, _, _ in results if success)
    
    for name, success, total, passed in results:
        status = "[OK] PASS" if success else "[FAIL] FAIL"
        print(f"  {status} - {name}")
    
    print("\n" + "-"*80)
    print(f"  Suites: {passed_suites}/{total_suites} passed ({passed_suites/total_suites*100:.0f}%)")
    print("-"*80)
    
    if passed_suites == total_suites:
        print("\n[SUCCESS] All tests passed! System is healthy.")
        return True
    else:
        print(f"\n[WARN]  {total_suites - passed_suites} suite(s) failed. Check logs above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
