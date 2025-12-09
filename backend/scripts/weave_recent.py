#!/usr/bin/env python3
"""
CLI for MemoryWeaver to run repair cycles programmatically.
"""
import argparse
import asyncio
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.maintenance.weaver import MemoryWeaver
from src.config import settings

parser = argparse.ArgumentParser(description='Run MemoryWeaver repair cycle')
parser.add_argument('--hours', default=24, type=int)
parser.add_argument('--threshold', type=float, default=0.75)
parser.add_argument('--max-commit', type=int, default=50)
parser.add_argument('--csv-out', type=str, default=None)
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('--run-id', default=None, type=str)
parser.add_argument('--candidate-limit', default=None, type=int, help='Override candidate_limit (per-summary) default used when searching possible origin nodes')
parser.add_argument('--llm-api-base', default=None, type=str, help='LLM API base URL (overrides LLM_API_BASE setting). Example: http://localhost:8081')
parser.add_argument('--llm-embeddings-base', default=None, type=str, help='LLM Embeddings API base URL (overrides LLM_EMBEDDINGS_API_BASE setting). Example: http://127.0.0.1:8081')
parser.add_argument('--llm-embeddings-local-fallback-enabled', action='store_true', default=False, help='Enable local GGUF fallback for embeddings (default disabled)')
parser.add_argument('--llm-embeddings-model-name', default=None, type=str, help='Model name to pass to embeddings endpoint explicitly (overrides detection)')
parser.add_argument('--llm-embeddings-chunk-size', default=None, type=int, help='Override default chunk size (chars) for embedding long documents')
parser.add_argument('--llm-embeddings-backoff-seq', default=None, type=str, help='Comma-separated backoff chunk sizes to try on embed failures, e.g. 4096,2048,1024,512')
parser.add_argument('--llm-embeddings-adaptive-backoff', action='store_true', default=False, help='Enable adaptive backoff behavior (parse server messages and auto reduce chunk size)')
parser.add_argument('--llm-embeddings-batch-size', default=None, type=int, help='Override default embedding batch_size passed to embeddings client')
args = parser.parse_args()

async def main():
    # Allow CLI override of LLM API base (port or path) for one-off runs
    if args.llm_api_base:
        settings.llm_api_base = args.llm_api_base
    if args.llm_embeddings_base:
        settings.llm_embeddings_api_base = args.llm_embeddings_base
    if args.llm_embeddings_local_fallback_enabled:
        settings.llm_embeddings_local_fallback_enabled = True
    if args.llm_embeddings_model_name:
        settings.llm_embeddings_model_name = args.llm_embeddings_model_name
    if args.llm_embeddings_chunk_size:
        settings.llm_embeddings_chunk_size_default = args.llm_embeddings_chunk_size
    if args.llm_embeddings_backoff_seq:
        try:
            seq = [int(x.strip()) for x in args.llm_embeddings_backoff_seq.split(',') if x.strip()]
            settings.llm_embeddings_chunk_backoff_sequence = seq
        except Exception:
            print(f"⚠️  Invalid backoff sequence: {args.llm_embeddings_backoff_seq}")
    if args.llm_embeddings_adaptive_backoff:
        settings.llm_embeddings_adaptive_backoff_enabled = True
    else:
        # Ensure there is at least a default in settings
        settings.llm_api_base = settings.llm_api_base
    weaver = MemoryWeaver()
    batch_size = args.llm_embeddings_batch_size if args.llm_embeddings_batch_size is not None else getattr(settings, 'llm_embeddings_default_batch_size', 4)
    candidate_limit = args.candidate_limit if args.candidate_limit is not None else getattr(settings, 'weaver_candidate_limit', 200)
    await weaver.weave_recent(hours=args.hours, threshold=args.threshold, max_commit=args.max_commit, candidate_limit=candidate_limit, dry_run=args.dry_run, csv_out=args.csv_out, run_id=args.run_id, batch_size=batch_size)

asyncio.run(main())
