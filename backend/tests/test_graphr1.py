"""
Test Graph-R1 reasoning capabilities
"""
import httpx
import asyncio
import json
import socket
import pytest

ECE_URL = "http://localhost:8000"

async def test_graph_reasoning():
    """Test the Graph-R1 reasoning endpoint"""
    # Skip if local ECE server isn't running - this is an integration-level test
    try:
        with socket.create_connection(("localhost", 8000), timeout=0.5):
            pass
    except Exception:
        pytest.skip("ECE_Core API not running on localhost:8000; skipping integration test")
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Add some test memories
        print("📝 Adding test memories...")
        
        memories = [
            {
                "category": "code",
                "content": "Python async/await allows concurrent execution without threads",
                "tags": ["python", "async", "concurrency"],
                "importance": 8
            },
            {
                "category": "code",
                "content": "FastAPI uses Pydantic for request/response validation",
                "tags": ["fastapi", "python", "validation"],
                "importance": 7
            },
            {
                "category": "personal",
                "content": "I prefer working with type hints in Python for better code clarity",
                "tags": ["python", "preferences"],
                "importance": 6
            },
            {
                "category": "events",
                "content": "Started learning Graph-R1 reasoning on November 10, 2025",
                "tags": ["learning", "graphr1", "ai"],
                "importance": 9
            }
        ]
        
        for mem in memories:
            response = await client.post(
                f"{ECE_URL}/memories",
                params=mem
            )
            print(f"  ✓ Added: {mem['category']} - {mem['content'][:50]}...")
        
        # 2. Test Graph-R1 reasoning
        print("\n🧠 Testing Graph-R1 reasoning...")
        
        question = "What do I know about Python async programming and when did I start learning about Graph-R1?"
        
        response = await client.post(
            f"{ECE_URL}/reason",
            json={
                "session_id": "test_graph",
                "question": question,
                "mode": "graph"
            }
        )
        
        result = response.json()
        
        print(f"\nQuestion: {question}")
        print(f"\nAnswer: {result['answer']}")
        print(f"\nReasoning iterations: {result['iterations']}")
        print(f"Confidence: {result['confidence']}")
        print(f"\nReasoning trace:")
        for i, trace in enumerate(result['reasoning_trace'], 1):
            print(f"  {i}. {trace['type']}: {trace.get('query', 'N/A')[:60]}...")
        
        # 3. Test Markovian reasoning
        print("\n🔄 Testing Markovian reasoning...")
        
        complex_question = "Explain how async programming in Python works step by step"
        
        response = await client.post(
            f"{ECE_URL}/reason",
            json={
                "session_id": "test_markov",
                "question": complex_question,
                "mode": "markov"
            }
        )
        
        result = response.json()
        
        print(f"\nQuestion: {complex_question}")
        print(f"\nAnswer: {result['answer'][:300]}...")
        print(f"\nChunks processed: {result['iterations']}")
        
        # 4. Check reasoning trace
        print("\n📊 Checking reasoning trace...")
        
        response = await client.get(f"{ECE_URL}/reasoning/trace/test_graph")
        trace_data = response.json()
        
        print(f"Session: {trace_data['session_id']}")
        print(f"Number of traces: {len(trace_data['traces'])}")

if __name__ == "__main__":
    print("=" * 60)
    print("  Graph-R1 Reasoning Test")
    print("=" * 60)
    print("\nMake sure ECE_Core is running on port 8000!")
    print("Starting tests...\n")
    
    asyncio.run(test_graph_reasoning())
    
    print("\n" + "=" * 60)
    print("  ✅ Tests Complete!")
    print("=" * 60)
