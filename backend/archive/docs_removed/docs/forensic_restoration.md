# Forensic Restoration & Annotated Cleaning (ECE_Core)

This document summarizes the 'Forensic Restoration' (Annotated Cleaning) workflow implemented to preserve context while removing noise and corrupted content.

## Objectives
- Preserve raw data (`m.content`) for forensic and retrieval purposes.
- Use `content_cleaned` for indexing and linking to avoid spam/garbage embedding.
- Annotate sanitized technical context rather than removing it entirely (e.g., replacing ANSI codes with `[Context: Terminal Output]`).
- Identify and quarantine `token-soup` nodes to avoid using them for embeddings or graph repairs.
- Provide a regeneration path that normalizes and re-distills quarantined nodes.

## Key Tools & Functions
- `src/content_utils.normalize_technical_content(text)`
  - Detects and annotates: ANSI, Unix/Windows paths, hex dumps;
  - Produces a normalized text with semantic annotations instead of opaque noise.

- `src/content_utils.clean_content(text, annotate_technical=False)`
  - A conservative text cleaner; when `annotate_technical=True` it runs normalization first to preserve context tags.

- `src/distiller_impl.Distiller.distill_moment`
  - Integrates resilience logic: If the distiller detects token-soup, it attempts `normalize_technical_content()` and retries distillation prior to fallback sanitization.

- Quarantine scripts
  - `scripts/quarantine_token_soup.py` — Scans and optionally tags nodes as `#corrupted`.
  - `scripts/quarantine_regenerate.py` — For quarantined nodes: normalizes raw content, redistills it, and optionally writes `content_cleaned`; it can also replace the `#corrupted` tag with `regenerated`.

- Repair & Weaver
  - `scripts/neo4j/repair/repair_missing_links_similarity_embeddings.py` — now supports `--exclude-tag` to skip quarantined nodes.
  - `src/maintenance/weaver.py` — now passes `weaver_exclude_tag` to `run_repair` by default.

## Typical Workflows

1. Dry-run: identify quarantined nodes

```pwsh
python .\scripts\quarantine_token_soup.py --category summary --limit 500 --csv-out logs/token_soup_report.csv --sample 10 --use-cleaned
```

2. Tag quarantined nodes (write mode)

```pwsh
python .\scripts\quarantine_token_soup.py --category summary --limit 500 --write --csv-out logs/token_soup_report.csv --sample 10 --use-cleaned
```

3. Re-generate summaries for quarantined nodes

```pwsh
python .\scripts\quarantine_regenerate.py --tag '#corrupted' --limit 200 --csv-out logs/regenerate_report.csv --write
```

4. Run the weaver (repair) excluding corrupted nodes

```pwsh
python .\scripts\neo4j\repair\repair_missing_links_similarity_embeddings.py --dry-run --csv-out logs/weaver_review_chunked.csv --exclude-tag '#corrupted' --limit 200 --candidate-limit 100 --top-n 3 --export-top 25
```

## Rollback & Auditability
- CSV logs are produced for every step to review proposed repairs and regeneration results.
- Relationships created by the Weaver include `r.auto_commit_*` fields enabling rollback via existing scripts.

## Future Directions
- Integrate regeneration automatically within the Distiller or as a scheduled job under the Archivist.
- Add a quarantine UI or a triage CLI to quickly inspect and approve re-distilled nodes.
- Improve chunk-weighted averaging for embeddings and add more E2E tests for the regeneration process.

## Summary
This design preserves both the raw, forensic truth and the usable, sanitized indexable text. We now have a robust path to identify token-soup failures, protect the graph's signal, and reprocess nodes to recover valid summaries with contextual tags.
