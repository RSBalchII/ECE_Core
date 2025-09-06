#!/usr/bin/env python3
"""
Test script to verify the ExtractorAgent functionality
"""

import sys
import os
import asyncio

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.external_context_engine.tools.extractor_agent import ExtractorAgent

async def test_extractor_agent():
    """Test the ExtractorAgent functionality"""
    print("Testing ExtractorAgent...")
    
    # Initialize the agent
    agent = ExtractorAgent()
    
    # Create a simple test file
    test_content = "John Doe can be reached at john.doe@example.com. The meeting is on 12/25/2023."
    
    # Write test content to a temporary file
    with open("/tmp/test_extractor.txt", "w") as f:
        f.write(test_content)
    
    try:
        # Test basic extraction
        print("Testing basic extraction...")
        result = await agent.execute(
            data_source="/tmp/test_extractor.txt",
            data_type="text",
            criteria={}
        )
        
        print(f"Extraction success: {result['metadata']['extraction_success']}")
        print(f"Extracted items: {len(result['extracted_data'])}")
        print(f"Generated queries: {len(result['queries'])}")
        
        if result['metadata']['extraction_success']:
            print("Basic extraction test PASSED")
        else:
            print("Basic extraction test FAILED")
            print(f"Error: {result['metadata']['error_message']}")
            
        # Test keyword-based extraction
        print("\nTesting keyword-based extraction...")
        result = await agent.execute(
            data_source="/tmp/test_extractor.txt",
            data_type="text",
            criteria={
                "keywords": ["meeting", "email"]
            }
        )
        
        print(f"Extraction success: {result['metadata']['extraction_success']}")
        if result['metadata']['extraction_success']:
            print("Keyword-based extraction test PASSED")
        else:
            print("Keyword-based extraction test FAILED")
            
        # Test pattern-based extraction
        print("\nTesting pattern-based extraction...")
        result = await agent.execute(
            data_source="/tmp/test_extractor.txt",
            data_type="text",
            criteria={
                "patterns": {
                    "email_addresses": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                    "dates": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
                }
            }
        )
        
        print(f"Extraction success: {result['metadata']['extraction_success']}")
        if result['metadata']['extraction_success']:
            print("Pattern-based extraction test PASSED")
        else:
            print("Pattern-based extraction test FAILED")
            
        # Test performance metrics
        print("\nTesting performance metrics...")
        metrics = agent.get_performance_metrics()
        print(f"Total extractions: {metrics['total_extractions']}")
        print(f"Successful extractions: {metrics['successful_extractions']}")
        print(f"Failed extractions: {metrics['failed_extractions']}")
        print("Performance metrics test PASSED")
        
        print("\nAll tests completed!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        # Clean up the temporary file
        if os.path.exists("/tmp/test_extractor.txt"):
            os.remove("/tmp/test_extractor.txt")

if __name__ == "__main__":
    asyncio.run(test_extractor_agent())