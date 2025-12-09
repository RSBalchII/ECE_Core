import asyncio
from src.memory import TieredMemory
from src.llm import LLMClient
from src.context import ContextManager

async def test_retrieval_debug():
    print("=" * 80)
    print("DEBUG: Memory Retrieval Pipeline Test")
    print("=" * 80)
    
    # Initialize components
    memory = TieredMemory()
    await memory.initialize()
    
    llm = LLMClient()
    context_mgr = ContextManager(memory, llm)
    
    # Test query
    query = "Tell me about autism"
    print(f"\n🔍 User Query: '{query}'")
    
    # Step 1: Direct full-text search
    print("\n" + "-" * 80)
    print("STEP 1: Direct full-text search for 'autism'")
    print("-" * 80)
    direct_results = await memory.search_memories('autism', limit=15)
    print(f"✓ Direct search returned {len(direct_results)} results")
    if direct_results:
        print(f"\nFirst 3 results:")
        for i, mem in enumerate(direct_results[:3], 1):
            print(f"\n{i}. ID: {mem.get('id')}")
            print(f"   memory_id: {mem.get('memory_id')}")
            print(f"   Category: {mem.get('category')}")
            print(f"   Importance: {mem.get('importance')}")
            print(f"   Score: {mem.get('score')}")
            print(f"   Content preview: {mem.get('content', '')[:150]}...")
    
    # Step 2: Test ContextManager's retrieval
    print("\n" + "-" * 80)
    print("STEP 2: ContextManager._retrieve_relevant_memories()")
    print("-" * 80)
    retrieved = await context_mgr._retrieve_relevant_memories(query, limit=15)
    print(f"✓ Retrieved {len(retrieved)} memories")
    
    if retrieved:
        print(f"\nFirst 3 retrieved:")
        for i, mem in enumerate(retrieved[:3], 1):
            print(f"\n{i}. ID: {mem.get('id')}")
            print(f"   Category: {mem.get('category')}")
            print(f"   Content preview: {mem.get('content', '')[:150]}...")
    else:
        print("❌ No memories retrieved by ContextManager!")
        
        # Debug: Check what keywords were extracted
        words = query.lower().split()
        keywords = [w.strip('.,!?;:()[]{}') for w in words if len(w) > 3]
        print(f"\nExtracted keywords (len > 3): {keywords}")
        
        # Try each keyword manually
        print("\nTrying each keyword individually:")
        for keyword in keywords[:5]:
            results = await memory.search_memories(keyword, limit=5)
            print(f"  '{keyword}': {len(results)} results")
    
    # Step 3: Full context build
    print("\n" + "-" * 80)
    print("STEP 3: Full context assembly")
    print("-" * 80)
    session_id = "test_session"
    context = await context_mgr.build_context(session_id, query)
    print(f"✓ Context length: {len(context)} chars")
    print(f"\nContext preview (first 800 chars):")
    print(context[:800])
    
    await memory.close()
    
    print("\n" + "=" * 80)
    print("✅ Debug test complete")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_retrieval_debug())
