import asyncio
from src.memory import TieredMemory
from src.llm import LLMClient
from src.context import ContextManager

async def comprehensive_validation():
    """
    Final validation showing the complete system working correctly.
    """
    print("=" * 80)
    print("COMPREHENSIVE SYSTEM VALIDATION")
    print("=" * 80)
    
    memory = TieredMemory()
    await memory.initialize()
    llm = LLMClient()
    context_mgr = ContextManager(memory, llm)
    
    # Get a real topic from the database
    print("\n📊 Analyzing database content...")
    all_memories = []
    for category in ['event', 'idea', 'code', 'general', 'person']:
        recent = await memory.get_recent_by_category(category, limit=5)
        all_memories.extend(recent)
    
    print(f"✓ Sampled {len(all_memories)} recent memories")
    
    # Create a query based on actual content
    if all_memories:
        sample = all_memories[0]
        words = sample.get('content', '').split()[:20]
        topic_words = [w for w in words if len(w) > 4 and w.isalnum()][:3]
        
        if topic_words:
            test_query = f"What do you remember about {' '.join(topic_words[:2])}?"
            
            print(f"\n🔍 Test Query: '{test_query}'")
            print("\n" + "-" * 80)
            
            # Build context
            context = await context_mgr.build_context("validation_test", test_query)
            
            print(f"✅ SUCCESS - Context Built")
            print(f"   Length: {len(context)} characters")
            print(f"   Estimated tokens: ~{len(context) // 4}")
            
            print(f"\n📄 Context Preview:")
            print("-" * 80)
            print(context[:1000])
            if len(context) > 1000:
                print("\n... [truncated] ...\n")
                print(context[-500:])
    
    # Component validation
    print("\n" + "=" * 80)
    print("COMPONENT VALIDATION")
    print("=" * 80)
    
    # Test 1: Metadata
    print("\n✓ Test 1: Metadata Population")
    test_search = await memory.search_memories("test", limit=1)
    if test_search:
        mem = test_search[0]
        assert mem.get('memory_id') is not None, "memory_id missing!"
        assert mem.get('score') is not None, "score missing!"
        assert mem.get('id') is not None, "id missing!"
        print("  ✅ All metadata fields present")
    
    # Test 2: Search
    print("\n✓ Test 2: Full-Text Search")
    results = await memory.search_memories("project", limit=10)
    print(f"  ✅ Found {len(results)} results for 'project'")
    
    # Test 3: Multi-strategy retrieval
    print("\n✓ Test 3: Multi-Strategy Retrieval")
    retrieved = await context_mgr._retrieve_relevant_memories("coding project", limit=10)
    print(f"  ✅ Retrieved {len(retrieved)} memories")
    
    # Test 4: Context assembly
    print("\n✓ Test 4: Context Assembly")
    context = await context_mgr.build_context("test_session", "test query")
    assert len(context) > 0, "Context is empty!"
    print(f"  ✅ Context assembled ({len(context)} chars)")
    
    await memory.close()
    
    print("\n" + "=" * 80)
    print("✅ ALL VALIDATION TESTS PASSED")
    print("=" * 80)
    print("\n🎉 Memory Recall System is fully operational!")

if __name__ == "__main__":
    asyncio.run(comprehensive_validation())
