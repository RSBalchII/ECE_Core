import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.distiller_impl import Distiller

async def main():
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value='{"summary": "Test summary", "entities": [{"name": "TestEntity", "type": "Concept", "description": "A test entity"}]}')
    dist = Distiller(mock_llm)
    res = await dist.distill_moment('Some text content')
    print('Result:', res)

asyncio.run(main())
