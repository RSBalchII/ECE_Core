#!/usr/bin/env python3
"""
Import `ece-core/combined_text2.txt` into Neo4j using `Neo4jStore.add_memory`.

This script is run from repo root (or ece-core/) and will read the JSON array in the file
and create Memory nodes in Neo4j. Use `--dry-run` to preview actions without committing.

Example:
  # Dry run only, preview what would be inserted
  python ece-core/scripts/import_combined_text2.py --dry-run

  # Commit insertions to Neo4j (default will commit if Neo4j reachable)
  python ece-core/scripts/import_combined_text2.py --commit

Note: Default database connection picks up values from `src/config.py` and `.env`.

Options added:
    --include-thinking : include `thinking_content` entries (disabled by default because these may be developer logs)
    --no-dedupe : disable deduplication by content hash (disabled by default)
    --session-id S : set the session ID for inserted memories
"""

import argparse
import asyncio
import json
import hashlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

# Setup a minimal logger for the script
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("import_combined_text2")

# NOTE: Avoid modifying sys.path to prevent local `scripts/neo4j` package from shadowing the
# installed `neo4j` driver. This script should be run from repo root so that imports like
# `from src.memory.neo4j_store import Neo4jStore` resolve correctly.

try:
    from src.config import settings
except Exception as e:  # pragma: no cover - environment dependent
    logger.error(f"Could not import project modules: {e}")
    raise

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "combined_text2.txt"


def compute_hash(text: str) -> str:
    """Compute a stable SHA256 hash for deduplication use."""
    h = hashlib.sha256()
    if isinstance(text, str):
        h.update(text.encode("utf-8"))
    else:
        h.update(json.dumps(text, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


async def import_file(file_path: Path, commit: bool = False, include_thinking: bool = False, dedupe: bool = True, session_id_override: str = None) -> List[Dict[str, Any]]:
    """Parse the file and insert nodes into Neo4j using `Neo4jStore`.

    Returns a list of results with fields: index, inserted (bool), memory_id
    """
    store = None
    logger.info(f"commit flag passed: {commit}")
    if commit:
        try:
            from src.memory.neo4j_store import Neo4jStore
            store = Neo4jStore()
        except Exception as e:
            logger.warning(f"Cannot import Neo4jStore: {e}; falling back to dry-run behavior")
    if store:
        try:
            await store.initialize()
        except Exception as e:
            logger.warning(f"Neo4j init thrown: {e}")

    # If we couldn't connect to Neo4j, proceed in dry-run; but still parse
    neo4j_connected = bool(getattr(store, "neo4j_driver", None)) if store else False
    logger.info(f"neo4j_connected? {neo4j_connected}")
    if not neo4j_connected:
        logger.warning("Neo4j driver is not available; running in dry-run / local preview mode")

    results = []

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as fh:
        raw = fh.read()

    try:
        # Attempt to parse as JSON array
        docs = json.loads(raw)
    except Exception as e:
        # In case it's not pure JSON array, try to wrap or parse line-by-line
        logger.info("Input appears non-standard JSON; attempting to parse as lines of JSON objects")
        docs = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                docs.append(json.loads(line))
            except Exception:
                # skip
                continue

    for idx, obj in enumerate(docs):
        # obj is expected to be a dict; attempt to find meaningful content
        if isinstance(obj, dict):
            # prefer official response or content fields; fall back to text or thinking_content
            # Do not treat the object json dump as explicit content for thinking-only entries
            explicit_text = obj.get("response_content") or obj.get("content") or obj.get("text") or obj.get("message")
            thinking_text = obj.get("thinking_content")
            content = explicit_text if explicit_text else (thinking_text if include_thinking else None)
            # By default we skip `thinking_content` insertion unless explicitly requested
            if not include_thinking and thinking_text and not explicit_text:
                results.append({"index": idx, "inserted": False, "reason": "thinking_content_skipped"})
                logger.debug(f"Skipping thinking_content-only item at index {idx}")
                continue
        else:
            content = str(obj)

        # Skip short or empty content
        if not content or len(content.strip()) == 0:
            logger.debug(f"Skipping empty content at index {idx}")
            results.append({"index": idx, "inserted": False, "reason": "empty content"})
            continue

        content_hash = compute_hash(content)

        metadata = obj.copy() if isinstance(obj, dict) else {"raw": obj}
        metadata.update({
            "source": str(file_path.name),
            "source_type": "document",
            "source_index": idx,
            "injected_by": "import_combined_text2.py",
            "ingested_at": datetime.now().isoformat(),
            "committed": bool(commit),
        })

        # Category heuristics: prefer 'doc' for textual content, 'logs' for 'thinking_content' markers.
        category = "doc"
        if isinstance(obj, dict) and obj.get("thinking_content") and not obj.get("response_content"):
            # these appear to be 'thinking' logs
            category = "log"

        tags = obj.get("tags") if isinstance(obj, dict) and obj.get("tags") else []
        if isinstance(tags, list):
            tags = tags + ["combined_text2", "injected"]
        elif isinstance(tags, str):
            tags = [tags, "combined_text2", "injected"]
        else:
            tags = ["combined_text2", "injected"]

        importance = 5

        # Build entities if present in object under 'entities'
        entities = None
        if isinstance(obj, dict) and isinstance(obj.get("entities"), list) and len(obj.get("entities")) > 0:
            entities = obj.get("entities")

        if not commit or not neo4j_connected:
            logger.info(f"[DRY-RUN] Would add memory idx={idx}: hash={content_hash} category={category} tags={tags} meta_keys={list(metadata.keys())}")
            results.append({"index": idx, "inserted": False, "memory_id": None, "hash": content_hash})
            continue

        # Add the memory
        try:
            memory_id = await store.add_memory(
                session_id=session_id_override or getattr(settings, "anchor_session_id", "import-session"),
                content=content,
                category=category,
                tags=tags,
                importance=importance,
                metadata=metadata,
                entities=entities,
                content_cleaned=None,
                # If dedupe is disabled, do not pass a content_hash to avoid dedupe lookup
                content_hash=content_hash if dedupe else None,
                content_embedding_text=None,
            )
            if memory_id:
                logger.info(f"Inserted memory {memory_id} for index {idx} (hash={content_hash})")
                results.append({"index": idx, "inserted": True, "memory_id": memory_id, "hash": content_hash})
            else:
                logger.warning(f"Failed to insert memory at index {idx}: returned None")
                results.append({"index": idx, "inserted": False, "memory_id": None, "hash": content_hash})
        except Exception as e:
            logger.error(f"Exception inserting memory at index {idx}: {e}")
            results.append({"index": idx, "inserted": False, "error": str(e), "hash": content_hash})

    # Close Neo4j driver cleanly
    if store:
        try:
            await store.close()
        except Exception:
            pass

    return results


def parse_args():
    p = argparse.ArgumentParser("Import combined_text2 into Neo4j as Memory nodes")
    p.add_argument("--file", default=str(DEFAULT_FILE), help="Path to the combined text JSON file (default: ece-core/combined_text2.txt)")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=False, help="Preview import without committing changes to Neo4j")
    p.add_argument("--commit", dest="commit", action="store_true", default=False, help="Commit changes to Neo4j (default is to dry-run when Neo4j not reachable)")
    p.add_argument("--include-thinking", dest="include_thinking", action="store_true", default=False, help="Include thinking_content fields; default false")
    p.add_argument("--no-dedupe", dest="no_dedupe", action="store_true", default=False, help="Disable dedupe by content hash")
    p.add_argument("--session-id", dest="session_id", default=None, help="Set session_id to assign to Memory nodes")
    return p.parse_args()


def main():
    args = parse_args()
    file_path = Path(args.file)
    commit = bool(args.commit)
    include_thinking = bool(args.include_thinking)
    dedupe = not bool(args.no_dedupe)
    session_id = args.session_id
    if not commit:
        # Default to dry-run unless user explicitly consented
        logger.warning("Running in dry-run mode (no writes) unless `--commit` supplied")

    logger.info(f"Loading file: {file_path}")

    loop = asyncio.get_event_loop()
    try:
        results = loop.run_until_complete(import_file(file_path, commit=commit, include_thinking=include_thinking, dedupe=dedupe, session_id_override=session_id))
    finally:
        # in Python 3.11, event loop cleanup handled differently; we attempt to close if still open
        try:
            loop.close()
        except Exception:
            pass

    total = len(results)
    inserted_count = len([r for r in results if r.get('inserted')])
    skipped_count = len([r for r in results if not r.get('inserted') and r.get('reason')])
    error_count = len([r for r in results if r.get('error')])
    logger.info(f"Processed {total} entries. Inserted_count={inserted_count} Skipped={skipped_count} Errors={error_count}")

    # Write a small JSON summary to stdout
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
