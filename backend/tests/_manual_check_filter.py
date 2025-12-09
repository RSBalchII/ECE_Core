import asyncio
from src.distiller import Distiller, filter_and_consolidate

async def main():
    d = Distiller(None)
    try:
        res = await d.filter_and_consolidate('a', [], [], active_context='x')
        print('Distiller method OK:', res)
    except Exception as e:
        print('Distiller method error:', e)

    try:
        res2 = filter_and_consolidate([])
        print('Module-level filter ok', res2)
    except Exception as e:
        print('Module-level filter error', e)

asyncio.run(main())
