import importlib, sys, os

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

candidates = [
    'scripts.neo4j.repair.repair_missing_links_similarity_embeddings',
    'scripts.repair_missing_links_similarity_embeddings',
]

for cand in candidates:
    try:
        mod = importlib.import_module(cand)
        print(f"SUCCESS: imported {cand} -> has run_repair = {hasattr(mod, 'run_repair')}")
    except Exception as e:
        print(f"FAIL: import {cand} -> {e}")

# Also try to import the package 'scripts' and nested packages
try:
    importlib.import_module('scripts')
    print('SUCCESS: imported scripts package')
except Exception as e:
    print('FAIL: import scripts package ->', e)
try:
    importlib.import_module('scripts.neo4j')
    print('SUCCESS: imported scripts.neo4j package')
except Exception as e:
    print('FAIL: import scripts.neo4j package ->', e)
try:
    importlib.import_module('scripts.neo4j.repair')
    print('SUCCESS: imported scripts.neo4j.repair package')
except Exception as e:
    print('FAIL: import scripts.neo4j.repair package ->', e)
