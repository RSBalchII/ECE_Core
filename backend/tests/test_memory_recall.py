"""Test memory recall improvements."""
import asyncio
import httpx

async def test_memory_recall():
    """Test that the system can recall complex narrative details."""
    
    test_queries = [
        {
            "query": "Tell me about Swan and Pauline from Earth 2312",
            "expected_keywords": ["Swan", "Pauline", "quantum", "AI", "augmentation"],
            "description": "Character recall test"
        },
        {
            "query": "What do you remember about the quantum AI in Swan's head?",
            "expected_keywords": ["quantum", "AI", "Swan", "augmentation", "copy"],
            "description": "Specific detail recall"
        },
        {
            "query": "Recall our conversation about Coda and Sybil",
            "expected_keywords": ["Coda", "Sybil", "C-001", "organic", "persona"],
            "description": "Persona development recall"
        },
        {
            "query": "What was the POML clarification date?",
            "expected_keywords": ["August", "14", "2025", "Microsoft", "JSON"],
            "description": "Specific date recall"
        }
    ]
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        print("=" * 60)
        print("MEMORY RECALL TEST")
        print("=" * 60)
        
        for i, test in enumerate(test_queries, 1):
            print(f"\n{i}. {test['description']}")
            print(f"   Query: {test['query']}")
            
            try:
                response = await client.post(
                    f"{base_url}/chat",
                    json={
                        "message": test["query"],
                        "session_id": "memory_test"
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("response", "")
                    
                    # Check for expected keywords
                    found_keywords = [kw for kw in test["expected_keywords"] if kw.lower() in answer.lower()]
                    missing_keywords = [kw for kw in test["expected_keywords"] if kw.lower() not in answer.lower()]
                    
                    recall_score = len(found_keywords) / len(test["expected_keywords"]) * 100
                    
                    print(f"   ✓ Response received ({len(answer)} chars)")
                    print(f"   Recall Score: {recall_score:.0f}% ({len(found_keywords)}/{len(test['expected_keywords'])} keywords)")
                    
                    if found_keywords:
                        print(f"   Found: {', '.join(found_keywords)}")
                    if missing_keywords:
                        print(f"   Missing: {', '.join(missing_keywords)}")
                    
                    if recall_score < 50:
                        print(f"   ⚠️  LOW RECALL - May need more memory")
                        print(f"   Response preview: {answer[:200]}...")
                    elif recall_score < 80:
                        print(f"   ⚠️  MODERATE RECALL - Some details missing")
                    else:
                        print(f"   ✅ HIGH RECALL - Good memory retrieval")
                    
                else:
                    print(f"   ❌ Error: HTTP {response.status_code}")
                    print(f"   {response.text[:200]}")
                    
            except Exception as e:
                print(f"   ❌ Exception: {e}")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)

if __name__ == "__main__":
    print("Make sure ECE_Core is running at http://localhost:8000")
    print("Starting test in 3 seconds...\n")
    asyncio.run(test_memory_recall())
