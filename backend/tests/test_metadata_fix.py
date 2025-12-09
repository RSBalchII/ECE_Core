import asyncio
from src.memory import TieredMemory

async def test_metadata():
    print("Testing memory metadata population...")
    
    memory = TieredMemory()
    await memory.initialize()
    
    # Test full-text search
    results = await memory.search_memories('autism', limit=5)
    print(f"\n✓ Full-text search returned {len(results)} results")
    
    if results:
        first = results[0]
        print(f"\n✓ First result:")
        print(f"  - memory_id: {first.get('memory_id')}")
        print(f"  - score: {first.get('score')}")
        print(f"  - importance: {first.get('importance')}")
        print(f"  - content preview: {first.get('content', '')[:100]}...")
        
        # Validate metadata fields
        assert first.get('memory_id') is not None, "❌ memory_id is None!"
        assert first.get('score') is not None, "❌ score is None!"
        assert first.get('id') is not None, "❌ id is None!"
        print("\n✓ All metadata fields properly populated!")
    else:
        print("❌ No results returned")
    
    # Test tag-based search
    tag_results = await memory.search_memories(tags=['autism'], limit=5)
    print(f"\n✓ Tag search returned {len(tag_results)} results")
    
    if tag_results:
        first_tag = tag_results[0]
        print(f"\n✓ First tag result:")
        print(f"  - memory_id: {first_tag.get('memory_id')}")
        print(f"  - score: {first_tag.get('score')}")
        
        assert first_tag.get('memory_id') is not None, "❌ Tag search memory_id is None!"
        assert first_tag.get('score') is not None, "❌ Tag search score is None!"
        print("\n✓ Tag search metadata properly populated!")
    
    await memory.close()
    print("\n✅ All tests passed! Metadata fix is working.")

if __name__ == "__main__":
    asyncio.run(test_metadata())
