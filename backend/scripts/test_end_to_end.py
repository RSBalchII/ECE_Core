#!/usr/bin/env python3
import asyncio
import os
import sys
import uuid
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.memory.manager import TieredMemory

async def run_test():
    store = TieredMemory()
    await store.initialize()
    if not store.neo4j_driver:
        print('Neo4j not connected; aborting test')
        return
    # create an import node
    content = 'This is a test import chunk. sudo apt-get update; Version v1.2.3; /usr/bin/test' + str(uuid.uuid4())
    metadata = {'source': 'test_e2e', 'chunk_index': 0}
    import_id = await store.add_memory(session_id='test', content=content, category='import', tags=['test_import'], importance=5, metadata=metadata)
    print('Import node created:', import_id)
    # create a summary node with similar content
    summary_content = 'This summary notes the test import: it contains a version v1.2.3 and a path /usr/bin/test; it used apt-get.'
    summary_id = await store.add_memory(session_id='test', content=summary_content, category='summary', tags=['test_summary'], importance=3, metadata={'source': 'test_summary'})
    print('Summary node created:', summary_id)

    await store.close()

if __name__ == '__main__':
    asyncio.run(run_test())
