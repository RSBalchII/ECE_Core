"""
Performance test for the DistillerAgent with large text
"""

import sys
import os
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.external_context_engine.tools.distiller_agent import DistillerAgent, DistillationInput

async def test_large_text_performance():
    # Initialize the DistillerAgent
    agent = DistillerAgent()
    
    # Create a large text sample
    large_text = "This is a sample sentence. " * 1000  # 1000 repetitions
    
    # Add some entities and relationships to make it more realistic
    large_text += "Google was founded by Larry Page and Sergey Brin while they were Ph.D. students at Stanford University. "
    large_text += "Microsoft was founded by Bill Gates and Paul Allen in 1975. "
    large_text += "Apple was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in 1976. "
    large_text += "Amazon was founded by Jeff Bezos in 1994. "
    large_text += "Facebook was founded by Mark Zuckerberg in 2004. "
    
    print(f"Testing with text of length: {len(large_text)} characters")
    
    # First execution (no cache)
    start_time = time.time()
    input_data = DistillationInput(text=large_text, context={})
    result1 = await agent.execute(input_data)
    first_execution_time = time.time() - start_time
    
    print(f"First execution time: {first_execution_time:.4f} seconds")
    print(f"Entities found: {len(result1.entities)}")
    print(f"Relationships found: {len(result1.relationships)}")
    print(f"Key points found: {len(result1.key_points)}")
    print()
    
    # Second execution (with cache)
    start_time = time.time()
    result2 = await agent.execute(input_data)
    second_execution_time = time.time() - start_time
    
    print(f"Second execution time (cached): {second_execution_time:.4f} seconds")
    print(f"Performance improvement: {first_execution_time / second_execution_time:.2f}x faster")
    print()
    
    # Verify results are the same
    print("Results are consistent:", result1.entities == result2.entities and 
          result1.relationships == result2.relationships and 
          result1.key_points == result2.key_points)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_large_text_performance())