import os, sys, importlib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
try:
    m = importlib.import_module('scripts.repair_missing_links_similarity_embeddings')
    print('Found module: scripts.repair_missing_links_similarity_embeddings, run_repair:', hasattr(m, 'run_repair'))
except Exception as e:
    print('Import scripts.repair_missing_links_similarity_embeddings failed:', e)
try:
    m2 = importlib.import_module('scripts.neo4j.repair.repair_missing_links_similarity_embeddings')
    print('Found module: scripts.neo4j.repair.repair_missing_links_similarity_embeddings, run_repair:', hasattr(m2, 'run_repair'))
except Exception as e:
    print('Import scripts.neo4j.repair.repair_missing_links_similarity_embeddings failed:', e)
