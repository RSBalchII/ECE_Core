import asyncio
import os
import sys
from pathlib import Path
# Ensure repo root is on sys.path so `plugins` package can be imported when invoked from Context-Engine/
repo_root = str(Path(__file__).resolve().parents[1].parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
from plugins.manager import PluginManager

async def run_tests():
    config = {"PROJECT_ROOT": os.getcwd(), "enabled": True, "PLUGINS_DIR": str(Path(os.getcwd()) / 'plugins')}
    pm = PluginManager(config)
    discovered = pm.discover()
    print("Discovered plugins:", discovered)

    tools = pm.list_tools()
    print("Available tools:", tools)

    # Test mgrep plugin (if loaded)
    if 'mgrep' in discovered:
        print('\nTesting mgrep:mgrep (search for "TODO" in repo)...')
        res = await pm.execute_tool('mgrep:mgrep', pattern='TODO', path='.', include='**/*.py')
        print('mgrep result (count):', res.get('count') if isinstance(res, dict) else len(res))
        print(res)
    else:
        print('mgrep plugin not loaded; skipping mgrep test.')

    # Test example web_search plugin (example_tools:web_search)
    if 'example_tools' in discovered:
        print('\nTesting example_tools:web_search search query "weather"...')
        res2 = await pm.execute_tool('example_tools:web_search', query='weather in Bernalillo', max_results=3)
        print('example web_search result:', res2)
    else:
        print('example_tools plugin not found; skipping web_search plugin test.')

if __name__ == '__main__':
    asyncio.run(run_tests())
