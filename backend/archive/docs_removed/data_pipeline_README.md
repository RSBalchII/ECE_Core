````markdown
# Data Pipeline

Scripts for populating SQLite database and Neo4j knowledge graph from conversation data.

## Files

**`import_turns.py`** - Import conversation turns to SQLite
- Reads parsed turn data from `sample_turns.jsonl`
- Populates `conversation_turns` table
- 401 turns, ~3M tokens imported

**`extract_entities.py`** - Extract entities and build Neo4j graph
- LLM-based entity extraction from conversation turns
- Populates SQLite `entities` and `turn_entities` tables
- Creates Neo4j Entity and HyperEdge nodes
- Links Neo4j entities to SQLite turn IDs

**`import_combined_context.py`** - Full context import (legacy)
- Markovian chunking of large context files
- SQLite + Neo4j population
- Graceful degradation (works without Neo4j)

**`parse_combined_text.py`** - Parse raw conversation files
- Extracts embedded JSON/MD from `combined_text.txt`
- Helper for extract_turns.py

## Usage

```bash
# 1. Import conversation turns to SQLite
python data_pipeline/import_turns.py

# 2. Extract entities and build graph (requires Neo4j)
export NEO4J_PASSWORD=your_password
python data_pipeline/extract_entities.py

# 3. Test the pipeline
python tests/test_entity_flow.py
```

## Data Flow

```
combined_text.txt
  ↓ (parse_combined_text.py / extract_turns.py)
sample_turns.jsonl
  ↓ (import_turns.py)
SQLite: conversation_turns (401 rows)
  ↓ (extract_entities.py)
├─→ SQLite: entities + turn_entities
└─→ Neo4j: Entity nodes + HyperEdge relations
```

````
