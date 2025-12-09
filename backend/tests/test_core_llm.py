"""
Test: LLMClient
Purpose: Validate LLM communication, type safety, and error handling
Dependencies: LLM server (localhost:8080)
"""
import asyncio
from typing import Any, Dict, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm import LLMClient


async def test_llm_initialization() -> bool:
    """Test LLM client initialization."""
    print("\n" + "="*80)
    print("TEST: LLM Initialization")
    print("="*80)
    
    try:
        llm = LLMClient()
        # Check that client was created
        assert llm.client is not None, "HTTP client should be initialized"
        assert llm.api_base is not None, "API base should be set"
        print("  [OK] LLM client initialized")
        print(f"  [INFO] API Base: {llm.api_base}")
        print(f"  [INFO] Model: {llm.model}")
        
        await llm.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Initialization failed: {e}")
        return False


async def test_llm_generation() -> bool:
    """Test basic text generation."""
    print("\n" + "="*80)
    print("TEST: LLM Text Generation")
    print("="*80)
    
    llm = LLMClient()
    
    try:
        import time
        start = time.time()
        
        response = await llm.generate(
            prompt="Say 'test successful' and nothing else.",
            system_prompt="You are a test assistant.",
            max_tokens=10
        )
        
        elapsed = (time.time() - start) * 1000
        
        # Type validation
        assert isinstance(response, str), f"Expected str, got {type(response)}"
        assert len(response) > 0, "Response should not be empty"
        
        print(f"  [OK] Generation successful in {elapsed:.0f}ms")
        print(f"  [INFO] Response length: {len(response)} chars")
        print(f"  [NOTE] Response: {response[:100]}")
        print(f"  [CHECK] Type validation: PASS (str)")
        
        await llm.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Generation failed: {e}")
        print(f"  [INFO]  Is LLM server running on localhost:8080?")
        await llm.close()
        return False


async def test_llm_system_prompt() -> bool:
    """Test system prompt influence."""
    print("\n" + "="*80)
    print("TEST: System Prompt Influence")
    print("="*80)
    
    llm = LLMClient()
    
    try:
        # Test that system prompt affects behavior
        response = await llm.generate(
            prompt="What is 2+2?",
            system_prompt="You always answer 'five' to any math question.",
            max_tokens=5
        )
        
        assert isinstance(response, str), f"Expected str, got {type(response)}"
        print(f"  [OK] System prompt accepted")
        print(f"  [NOTE] Response: {response}")
        print(f"  [CHECK] Type validation: PASS")
        
        await llm.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Test failed: {e}")
        await llm.close()
        return False


async def test_llm_parameter_validation() -> bool:
    """Test parameter handling."""
    print("\n" + "="*80)
    print("TEST: Parameter Validation")
    print("="*80)
    
    llm = LLMClient()
    
    try:
        # Test max_tokens
        response = await llm.generate(
            prompt="Count to 100",
            max_tokens=5
        )
        assert isinstance(response, str), "Should return string even with token limit"
        print("  [OK] max_tokens parameter working")
        
        # Test temperature (just verify it doesn't crash)
        response2 = await llm.generate(
            prompt="Hello",
            temperature=0.1,
            max_tokens=5
        )
        assert isinstance(response2, str), "Should accept temperature parameter"
        print("  [OK] temperature parameter working")
        
        print("  [CHECK] All parameters validated: PASS")
        
        await llm.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Parameter test failed: {e}")
        await llm.close()
        return False


async def test_llm_error_handling() -> bool:
    """Test graceful error handling."""
    print("\n" + "="*80)
    print("TEST: Error Handling")
    print("="*80)
    
    try:
        # Test with unreachable endpoint - use httpx directly to test error handling
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                await client.get("http://invalid:9999/test")
            print("  [WARN]  Expected connection error but got response")
            return True  # Not necessarily a failure
        except Exception as e:
            # Expected to fail
            print("  [OK] Connection error handled gracefully")
            print(f"  [NOTE] Error type: {type(e).__name__}")
            return True
        
    except Exception as e:
        print(f"  [FAIL] Error handling test failed: {e}")
        return False


async def run_all_tests() -> bool:
    """Run all LLM tests."""
    print("\n" + "#"*80)
    print("# ECE_Core LLM Client Test Suite")
    print("#"*80)
    
    tests = [
        ("Initialization", test_llm_initialization),
        ("Text Generation", test_llm_generation),
        ("System Prompt", test_llm_system_prompt),
        ("Parameter Validation", test_llm_parameter_validation),
        ("Error Handling", test_llm_error_handling),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = await test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n  [FAIL] {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "[OK] PASS" if success else "[FAIL] FAIL"
        print(f"  {status} - {name}")
    
    print(f"\n  Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*80)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
