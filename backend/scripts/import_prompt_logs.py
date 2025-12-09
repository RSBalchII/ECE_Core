#!/usr/bin/env python3
"""
Import a free-form prompt-logs.txt into Neo4j as Memory nodes.

The script will parse the log lines, extract user/assistant turns and store them as
memory nodes. By default, it skips lines that look like internal thinking or developer logs.
Use `--include-thinking` to include `thinking_content` fragments.

This script is similar to `import_combined_text2.py` but targetted at newline-based logs.
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from src.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("import_prompt_logs")

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "prompt-logs.txt"


def _is_thinking_line(line: str) -> bool:
    if 'thinking' in line.lower() or 'thinking_content' in line.lower() or '<thinking>' in line.lower():
        return True
    return False


def _is_chat_user_line(line: str) -> bool:
    return line.strip().startswith("You:") or line.strip().startswith("User:")


def _is_chat_assistant_line(line: str) -> bool:
    return line.strip().startswith("Assistant:")


def extract_turns(lines: List[str], include_thinking: bool = False) -> List[Dict[str, Any]]:
    """Extracts user/assistant turns from free-form logs.
    Returns items like: {"user": "...", "assistant": "...", "meta": {...}}
    """
    turns = []
    pending_user = None
    pending_assistant = None
    for raw in lines:
        line = raw.rstrip('\n')
        if not line.strip():
            continue
        if _is_chat_user_line(line):
            text = line.split(':', 1)[1].strip()
            if pending_user and pending_assistant:
                # Push previous turn
                turns.append({"user": pending_user, "assistant": pending_assistant})
                pending_user = None
                pending_assistant = None
            pending_user = text
            continue
        if _is_chat_assistant_line(line):
            # Capture assistant content; include thinking in the content only if include_thinking True
            text = line.split(':', 1)[1].strip()
            if _is_thinking_line(text) and not include_thinking:
                # store a marker in metadata but don't include as assistant content
                if not pending_assistant:
                    pending_assistant = ''
                # Add to metadata by appending a marker
                # For logs that include 'thinking_content: "...' inside JSON fragments, try to keep them as metadata
                continue
            if not pending_assistant:
                pending_assistant = text
            else:
                pending_assistant += "\n" + text
            continue
        # Non-chat lines: skip unless they contain JSON fragments with thinking_content
        if '"thinking_content":' in line and include_thinking:
            # naive extraction: try to find the JSON chunk following the key
            try:
                # find first quote before thinking_content and the object bracket(s)
                idx = line.find('"thinking_content":')
                part = line[idx:]
                # attempt to find the starting quote of content
                quoted = part.split(':', 1)[1].strip()
                if quoted.startswith('"'):
                    q = quoted.split('"', 2)[1]
                    # append to assistant
                    if pending_assistant:
                        pending_assistant += '\n' + q
                    else:
                        pending_assistant = q
            except Exception:
                pass
            continue
        # else: ignore other noise
        continue

    if pending_user and pending_assistant:
        turns.append({"user": pending_user, "assistant": pending_assistant})

    return turns


def compute_meta(source: str, index: int, commit: bool = False) -> Dict[str, Any]:
    return {
        "source": source,
        "source_type": "prompt_logs",
        "source_index": index,
        "injected_by": "import_prompt_logs.py",
        "ingested_at": datetime.now().isoformat(),
        "committed": bool(commit),
    }


async def import_file(file_path: Path, commit: bool = False, include_thinking: bool = False, dedupe: bool = True, session_id_override: str = None) -> List[Dict[str, Any]]:
    results = []
    store = None
    logger.info(f"commit flag: {commit}, include_thinking: {include_thinking}, dedupe: {dedupe}")
    if commit:
        try:
            from src.memory.neo4j_store import Neo4jStore
            store = Neo4jStore()
            await store.initialize()
        except Exception as e:
            logger.warning(f"Neo4j init failed: {e}; running as dry-run")
            store = None
    neo4j_connected = bool(getattr(store, 'neo4j_driver', None)) if store else False

    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    text = file_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    turns = extract_turns(lines, include_thinking=include_thinking)
    logger.info(f"Found {len(turns)} turns")
    for idx, t in enumerate(turns):
        content = f"USER: {t.get('user')}\nASSISTANT: {t.get('assistant')}"
        metadata = compute_meta(file_path.name, idx, commit)
        tags = ["prompt-logs", "injected"]
        category = "chat"
        content_hash = None
        if dedupe:
            import hashlib, json
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        if not commit or not neo4j_connected:
            logger.info(f"[DRY-RUN] Would add memory idx={idx} hash={content_hash} tag={tags}")
            results.append({"index": idx, "inserted": False, "hash": content_hash})
            continue

        try:
            memory_id = await store.add_memory(
                session_id=session_id_override or getattr(settings, 'anchor_session_id', 'import-session'),
                content=content,
                category=category,
                tags=tags,
                importance=5,
                metadata=metadata,
                entities=None,
                content_cleaned=None,
                content_hash=content_hash if dedupe else None,
                content_embedding_text=None,
            )
            results.append({"index": idx, "inserted": bool(memory_id), "memory_id": memory_id, "hash": content_hash})
        except Exception as e:
            logger.error(f"Failed to add memory for idx={idx}: {e}")
            results.append({"index": idx, "inserted": False, "error": str(e)})

    if store:
        try:
            await store.close()
        except Exception:
            pass

    return results


def parse_args():
    p = argparse.ArgumentParser("Import prompt-logs into Neo4j as Memory nodes")
    p.add_argument("--file", default=str(DEFAULT_FILE))
    p.add_argument("--dry-run", dest="dry_run", action='store_true', default=False, help="Preview import without committing")
    p.add_argument("--commit", action='store_true', default=False, help="Commit changes to Neo4j")
    p.add_argument("--include-thinking", action='store_true', default=False)
    p.add_argument("--no-dedupe", dest="no_dedupe", action='store_true', default=False)
    p.add_argument("--session-id", dest="session_id", default=None)
    return p.parse_args()


def main():
    args = parse_args()
    file = Path(args.file)
    # If --dry-run specified explicitly, treat as not commit; else use --commit
    if getattr(args, 'dry_run', False):
        commit = False
    else:
        commit = bool(args.commit)
    include_thinking = bool(args.include_thinking)
    dedupe = not bool(args.no_dedupe)
    session_id = args.session_id
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(import_file(file, commit=commit, include_thinking=include_thinking, dedupe=dedupe, session_id_override=session_id))
    logger.info(f"Done: processed={len(results)} created={len([r for r in results if r.get('inserted')])} (dry_run={not commit})")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
