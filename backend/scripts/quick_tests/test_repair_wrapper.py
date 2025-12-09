import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.maintenance import repair_wrapper
import asyncio

async def d(threshold=None):
    return 'ok'

repair_wrapper._run_repair_fn = d
res = repair_wrapper.run_repair(threshold=0.5, exclude_tag='g')
print('is coroutine:', asyncio.iscoroutine(res))
print('result:', asyncio.get_event_loop().run_until_complete(res))

async def e(threshold=None, exclude_tag=None):
    return ('ok', exclude_tag)

repair_wrapper._run_repair_fn = e
res = repair_wrapper.run_repair(threshold=0.5, exclude_tag='tag1')
print('is coroutine:', asyncio.iscoroutine(res))
print('result:', asyncio.get_event_loop().run_until_complete(res))
