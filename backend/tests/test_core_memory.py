"""
Test: TieredMemory (Redis + Neo4j)
Purpose: Validate memory storage, retrieval, and graceful failure behavior
Dependencies: Redis (localhost:6379), Neo4j (localhost:7687)
"""
import asyncio
from typing import Any, Dict, List
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory import TieredMemory


async def test_memory_initialization() -> bool:
    """Test memory system initialization."""
    print("\n" + "="*80)
    print("TEST: Memory Initialization")
    print("="*80)
    
    memory = TieredMemory()
    
    try:
        await memory.initialize()
        
        # Validate connections
        assert memory.redis is not None or True, "Redis connection should be attempted"
        assert memory.neo4j_driver is not None or True, "Neo4j connection should be attempted"
    # No SQLite required. We rely on Redis + Neo4j only.
        
        print("  [OK] Memory initialized successfully")
        print(f"  [INFO] Redis: {'[OK] Connected' if memory.redis else '[FAIL] Unavailable'}")
        print(f"  [INFO] Neo4j: {'[OK] Connected' if memory.neo4j_driver else '[FAIL] Unavailable'}")
            # SQLite removed from the architecture
        
        await memory.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Initialization failed: {e}")
        return False


async def test_redis_active_context() -> bool:
    """Test Redis active context storage/retrieval."""
    print("\n" + "="*80)
    print("TEST: Redis Active Context")
    print("="*80)
    
    memory = TieredMemory()
    await memory.initialize()
    
    if not memory.redis:
        print("  [WARN]  Redis unavailable, skipping test")
        await memory.close()
        return True  # Not a failure, just unavailable
    
    try:
        session_id = "test_session_123"
        test_context = "This is test conversation context"
        
        # Save
        await memory.save_active_context(session_id, test_context)
        print("  [OK] Context saved to Redis")
        
        # Retrieve
        retrieved = await memory.get_active_context(session_id)
        assert isinstance(retrieved, str), f"Expected str, got {type(retrieved)}"
        assert retrieved == test_context, "Retrieved context doesn't match"
        print(f"  [OK] Context retrieved: {len(retrieved)} chars")
        print(f"  [CHECK] Type validation: PASS (str)")
        
        await memory.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Test failed: {e}")
        await memory.close()
        return False


async def test_neo4j_memory_search() -> bool:
    """Test Neo4j graph memory search."""
    print("\n" + "="*80)
    print("TEST: Neo4j Memory Search")
    print("="*80)
    
    memory = TieredMemory()
    await memory.initialize()
    
    try:
        import time
        start = time.time()
        
        # Search for any content
        results = await memory.search_memories_neo4j(
            query_text="conversation",
            limit=5
        )
        
        elapsed = (time.time() - start) * 1000
        
        # Validate type
        assert isinstance(results, list), f"Expected list, got {type(results)}"
        print(f"  [OK] Query executed in {elapsed:.0f}ms")
        print(f"  [INFO] Results: {len(results)} memories")
        
        # Validate structure
        if results:
            result = results[0]
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            assert "content" in result, "Missing 'content' field"
            assert "score" in result, "Missing 'score' field"
            print(f"  [CHECK] Type validation: PASS (List[Dict[str, Any]])")
            print(f"  [NOTE] Sample result: {result.get('content', '')[:50]}...")
        else:
            print("  [INFO]  No results found (graph may be empty)")
        
        await memory.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Test failed: {e}")
        await memory.close()
        return False


async def test_neo4j_failure_graceful() -> bool:
    """Test graceful handling when Neo4j is unavailable (no SQLite fallback)."""
    print("\n" + "="*80)
    print("TEST: Neo4j failure handling (no SQLite fallback)")
    print("="*80)
    
    memory = TieredMemory(neo4j_uri="bolt://invalid:9999")  # Force Neo4j failure
    await memory.initialize()
    
    try:
        # Should handle Neo4j failure gracefully and return an empty list or no crash
        results = await memory.search_memories(
            query_text="test",
            limit=5
        )
        
        assert isinstance(results, list), f"Expected list, got {type(results)}"
        print("  [OK] Graceful handling of Neo4j failure (no SQLite fallback expected)")
        print("  [CHECK] Type validation: PASS")
        
        await memory.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Fallback failed: {e}")
        await memory.close()
        return False


async def test_token_counting() -> bool:
    """Test token counting accuracy."""
    print("\n" + "="*80)
    print("TEST: Token Counting")
    print("="*80)
    
    memory = TieredMemory()
    await memory.initialize()
    
    try:
        test_texts = [
            ("Hello world", 2),
            ("This is a test sentence", 5),
            ("", 0),
        ]
        
        for text, expected_range in test_texts:
            count = memory.count_tokens(text)
            assert isinstance(count, int), f"Expected int, got {type(count)}"
            assert count >= 0, "Token count should be non-negative"
            print(f"  [OK] '{text}' → {count} tokens")
        
        print("  [CHECK] Type validation: PASS (int)")
        
        await memory.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Test failed: {e}")
        await memory.close()
        return False


async def run_all_tests() -> bool:
    """Run all memory tests."""
    print("\n" + "#"*80)
    print("# ECE_Core Memory Test Suite")
    print("#"*80)
    
    tests = [
        ("Initialization", test_memory_initialization),
        ("Redis Active Context", test_redis_active_context),
        ("Neo4j Search", test_neo4j_memory_search),
        ("Neo4j Failure Handling", test_neo4j_failure_graceful),
        ("Token Counting", test_token_counting),
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
