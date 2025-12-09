import importlib, sys, os

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

mods = ['src.maintenance.repair', 'src.maintenance.repair_wrapper']
for m in mods:
    try:
        mod = importlib.import_module(m)
        print(f'import {m} ok; run_repair available={hasattr(mod, "run_repair")}')
    except Exception as e:
        print(f'import {m} FAILED: {e}')
