import sys, types, asyncio, os
# Ensure repo root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
from src.maintenance.weaver import MemoryWeaver

# Create dummy module
dummy_mod = types.SimpleNamespace()
async def dummy_run_repair(**kwargs):
    print('dummy run_repair called with', kwargs.get('run_id'))
    return {'run_id': kwargs.get('run_id')}
dummy_mod.run_repair = dummy_run_repair

# Inject into sys.modules
sys.modules['scripts.neo4j.repair.repair_missing_links_similarity_embeddings'] = dummy_mod
sys.modules['scripts.repair_missing_links_similarity_embeddings'] = dummy_mod

# Create weaver and call weave_recent
weaver = MemoryWeaver()
async def doit():
    res = await weaver.weave_recent(hours=1, dry_run=True, csv_out=None)
    print('weave_recent result:', res)

asyncio.run(doit())
