#!/usr/bin/env python3
"""
Test script to verify dynamic model detection
"""
import asyncio
from src.llm import LLMClient

async def test_model_detection():
    """Test that model detection works"""
    client = LLMClient()
    
    print("Testing dynamic model detection...")
    print(f"Configured model: {client.model}")
    
    # Detect actual model
    detected = await client.detect_model()
    print(f"Detected model: {detected}")
    
    # Verify get_model_name works
    current = client.get_model_name()
    print(f"Current model name: {current}")
    
    print("\n✅ Model detection test complete!")

if __name__ == "__main__":
    asyncio.run(test_model_detection())
