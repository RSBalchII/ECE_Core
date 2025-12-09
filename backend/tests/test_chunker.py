"""
Test IntelligentChunker with this terminal conversation.

This script will:
1. Load this entire conversation from the user's message
2. Process it with IntelligentChunker
3. Show the compression results
4. Verify the output is coherent
"""
import asyncio
from src.intelligent_chunker import IntelligentChunker
from src.llm import LLMClient


async def test_chunker():
    # Initialize
    llm = LLMClient()
    chunker = IntelligentChunker(llm)
    
    # Load the large conversation (paste it here or read from file)
    large_input = """
    [PASTE THE TERMINAL CONVERSATION HERE]
    """
    
    print(f"📊 Testing IntelligentChunker")
    print(f"Input size: {len(large_input):,} characters")
    print(f"Estimated chunks: {len(large_input) // 4000}")
    print()
    
    # Process
    result = await chunker.process_large_input(
        user_input=large_input,
        query_context="the user wants to test chunking with this terminal conversation"
    )
    
    print(f"✅ Processing complete!")
    print(f"Output size: {len(result):,} characters")
    print(f"Compression: {len(result) / len(large_input):.1%}")
    print()
    print("=" * 80)
    print("PROCESSED OUTPUT:")
    print("=" * 80)
    print(result)
    print("=" * 80)
    
    # Verify coherence
    print()
    print("🔍 Coherence check:")
    print("Does the output preserve:")
    print("  - The hallucination discussion? [manual check]")
    print("  - The chunking strategy proposal? [manual check]")
    print("  - Key code snippets? [manual check]")
    print("  - Terminal errors? [manual check]")


if __name__ == "__main__":
    asyncio.run(test_chunker())
