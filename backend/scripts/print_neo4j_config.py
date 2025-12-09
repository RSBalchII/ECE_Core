# Script to print the Neo4j settings loaded by the application (masked password)
# Run this in the same Python environment where ECE_Core runs
import sys
from pathlib import Path

# Try to add the project root to sys.path so `src` can be imported from any cwd
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.config import settings
except Exception as e:
    print("Failed to import settings - ensure you run this in the ECE_Core project or that the repo root is on PYTHONPATH.")
    print(e)
    raise

def mask(s: str, show: int = 3):
    if not s:
        return ''
    if len(s) <= show:
        return '*' * len(s)
    return s[:1] + '*' * (len(s)-show-1) + s[-show:]

print('neo4j_uri:', settings.neo4j_uri)
print('neo4j_user:', settings.neo4j_user)
print('NEO4J_PASSWORD set:', bool(settings.neo4j_password))
print('NEO4J_PASSWORD (masked):', mask(settings.neo4j_password, show=3))
