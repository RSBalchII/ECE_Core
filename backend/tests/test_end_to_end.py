import asyncio
from src.memory import TieredMemory
from src.llm import LLMClient
from src.context import ContextManager
from src.config import Settings

async def test_end_to_end():
    print("Testing end-to-end memory retrieval...")
    
    # Initialize components
    memory = TieredMemory()
    await memory.initialize()
    
    llm = LLMClient()
    context_mgr = ContextManager(memory, llm)
    
    # Test query
    session_id = "test_session"
    user_input = "Tell me about autism"
    print(f"\n🔍 Testing query: '{user_input}'")
    
    # Build context
    context = await context_mgr.build_context(session_id, user_input)
    
    print(f"\n✓ Context built successfully")
    print(f"  - Total length: {len(context)} characters")
    print(f"  - Token count estimate: ~{len(context) // 4} tokens")
    
    if context and len(context) > 100:
        print(f"\n✓ Context preview (first 500 chars):")
        print(context[:500])
        print("\n✅ Success! Memories are being retrieved and assembled into context.")
    else:
        print("\n❌ Warning: Context is empty or too short")
        print(f"Full context: {context}")
    
    await memory.close()

if __name__ == "__main__":
    asyncio.run(test_end_to_end())
