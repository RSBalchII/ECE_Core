import asyncio
from src.memory import TieredMemory
from src.llm import LLMClient
from src.context import ContextManager

async def test_with_real_topic():
    print("=" * 80)
    print("Testing with topic that has real content: 'freelance work'")
    print("=" * 80)
    
    memory = TieredMemory()
    await memory.initialize()
    llm = LLMClient()
    context_mgr = ContextManager(memory, llm)
    
    # Test with a query about something in the memories
    query = "Tell me about freelance work and the gig economy"
    print(f"\n🔍 Query: '{query}'")
    
    # Direct search first
    print("\n" + "-" * 80)
    print("Direct full-text search for 'freelance':")
    results = await memory.search_memories('freelance', limit=10)
    print(f"✓ Found {len(results)} results")
    
    if results:
        print("\nFirst 3 results:")
        for i, mem in enumerate(results[:3], 1):
            print(f"\n{i}. Category: {mem.get('category')} | Importance: {mem.get('importance')}")
            print(f"   {mem.get('content', '')[:200]}...")
    
    # Full context build
    print("\n" + "-" * 80)
    print("Full context assembly:")
    session_id = "test_session"
    context = await context_mgr.build_context(session_id, query)
    
    print(f"\n✓ Context length: {len(context)} chars (~{len(context)//4} tokens)")
    print(f"\nContext (first 1500 chars):")
    print(context[:1500])
    print("\n...")
    print(context[-500:])
    
    await memory.close()
    
    print("\n" + "=" * 80)
    print("✅ Test complete")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_with_real_topic())
