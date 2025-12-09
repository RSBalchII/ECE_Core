import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from src.distiller_impl import Distiller

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    print("Starting manual Distiller verification...")
    
    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value='{"summary": "Manual Test Summary", "entities": [{"name": "ManualEntity", "type": "Test", "description": "Manual Desc"}]}')
    
    distiller = Distiller(mock_llm)
    
    try:
        print("Testing distill_moment...")
        result = await distiller.distill_moment("Test content")
        print(f"Result: {result}")
        
        if result["summary"] == "Manual Test Summary" and result["entities"][0]["text"] == "ManualEntity":
            print("SUCCESS: distill_moment working as expected.")
        else:
            print("FAILURE: distill_moment returned unexpected result.")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
