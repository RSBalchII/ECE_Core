# Standard 015: Radial Distillation

**Status:** ✅ IMPLEMENTED | **Version:** 1.0 | **Date:** 2026-09-04
**Introduced:** v5.2 (consolidation) | **Supersedes:** Standards 008, 133, 134, 027, 028, 029
**Component:** Engine / Distillation Service
**Source:** `engine/src/services/distillation/radial-distiller-v2.ts` (primary), `streaming-distiller.ts`, `distill-manager.ts`

---

## Philosophy Alignment

This standard embodies three core Anchor Engine principles:

> **"Forgetting is a feature, not a bug."** The brain forgets constantly, leaving only what matters. Radial distillation deliberately removes redundancy, preserving unique facts while letting noise fade.

> **"Clarity through distillation, not accumulation."** Human memory doesn't store every word; it stores the gist, the decisions, the *why*. Each pass makes the signal clearer.

> **"Separation of concerns in storage."** Raw source files (pointer-only per Standard 021) and derived summaries (distillation outputs) live separately to keep a clear architectural boundary between source and derived material.

---

## 1. Executive Summary

Radial distillation compresses the corpus into a deduplicated, LLM-friendly summary written to the **distills directory** (`DISTILLS_DIR`, default `<data>/distills` — see §9), separate from `mirrored_brain/`. It is *deliberate forgetting*: redundancy across the whole corpus is removed while unique facts and their provenance are preserved.

The service implements **four methods**, selected by request (§2). The current **default for seedless requests is full-corpus mode** — no query, compound IDs, buckets, or tags means "expand + dedup every unique atom."

| Method | Dedup unit | Output shape | Selected when |
|---|---|---|---|
| **Full-corpus** (§4) | Compound *content* (SimHash) | JSONL of inflated records w/ inline `dedup_of` | `mode === 'full-corpus'`, OR seedless & `mode !== 'standard'` (**default**) |
| **Standard** (§5) | Semantic block (SimHash) | Decision Records | otherwise (has a query / compound_ids / buckets, no tags) |
| **Tag-based** (§6) | Semantic block (per tag) | Decision Records + inflated content | `mode === 'tag-based'`, OR `seed.tags` present |
| **Legacy line-level** (§7) | Line (hash) | Compound/YAML | only via the streaming path (`streaming-distiller.ts`) — kept for backward compat |

---

## 2. Mode Selection (dispatcher)

`radialDistill()` in `radial-distiller-v2.ts:2067` dispatches in this order:

1. **Full-corpus** if `request.mode === 'full-corpus'` **or** the request is seedless (`!seed.query && !seed.compound_ids && !seed.buckets && !seed.tags`) and `mode !== 'standard'`.
2. **Tag-based** if `request.mode === 'tag-based'` **or** `seed.tags.length > 0`.
3. **Standard** otherwise.

```text
no seed (query/ids/buckets/tags all empty) ──► full-corpus   ← default
mode == 'full-corpus'                        ► full-corpus
has seed.tags  OR mode == 'tag-based'        ► tag-based
otherwise                                    ► standard
streaming path (executeStreamingDistill)     ► legacy line-level
```

---

## 3. Data Model & Provenance

Distillation reads from the atom data model and writes metadata pointers to the `distills` table:

- **atoms** ← owned by **molecules** ← historically grouped under **compounds** (deprecated, being removed — see spec.md §Data Model).
- Distillation queries **`molecules`** directly (standard/tag modes) or pages **`atoms`** by pointer (full-corpus mode); it never depends on the deprecated `compounds` table.
- The **`distills`** table stores only *metadata* (timestamp, file_path pointer) — never distilled content (pointer-only storage, Standard 021).

Two provenance mechanisms exist:

- **Inline `dedup_of[]`** (full-corpus): a survivor record lists the older near-duplicate compounds it absorbed, as a flat array of compound IDs.
- **`provenance[]`** (all modes): arrays listing source files/compounds each line or block came from.

*See spec.md §Data Model for the exact column schema (`molecular_signature`, `simhash`, `dedup_of`, `provenance`).*

---

## 4. Full-Corpus Mode (default)

Expands and deduplicates **every unique atom** in the corpus, streaming results to disk with flat working memory. Implemented in `radialDistillFullCorpus()`.

### Pipeline
1. **Pass 1 — enumerate (pointers only):** page through `atoms` by `id`, group occurrences by `compound_id`, and merge overlapping/adjacent byte ranges per source file (≤100 byte gaps). Track the latest atom timestamp per compound. **No content is held in RAM** — only pointers, merged ranges, and max timestamps.
2. **Build candidates:** one candidate record per compound = merged byte ranges + latest timestamp, content-less initially (`content_inflated: false`).
3. **Phase 1 — content SimHash dedup (memory-light):** for each candidate, inflate only its bounded window from disk, compute a SimHash via the WASM fingerprint module (SHA-256 crypto fallback), then **discard the content**, keeping only the hash + tiny metadata. Run an O(n²) Hamming-distance scan over hashes and use **union-find** (`survivorId` → cluster root) so every near-duplicate resolves to one survivor.
4. **Chain collapse:** a third-or-more identical compound absorbs the *whole* cluster (follow `survivorId` to its root), never escaping because its immediate predecessor was already dropped.
5. **Keep newest, record older:** within each near-duplicate cluster keep the record with the latest timestamp; fold the absorbed older IDs into that survivor's flat `dedup_of[]`.
6. **Phase 2 — stream survivors:** re-inflate each survivor from disk on demand (bounded window) and write JSONL, emitting inline `dedup_of` only when non-empty.

### Tunables (request fields)
| Field | Default | Cap | Meaning |
|---|---|---|---|
| `inflate_radius` | 500 | 1000 | bytes each side of a pointer to inflate for context |
| `page_size` | 500 | — | atoms per DB page (yields to event loop between pages) |
| `max_record_bytes` | 8192 | 256 min | hard cap on inflated content per record |
| `simhash_hamming_threshold` | 3 | 0–64 | Hamming bits to treat two SimHashes as duplicates |

### Known ceiling
The Hamming scan is O(n²) over hashes only (content never in RAM). Fine for the current compound count; an LSH index would be needed at much larger scale. Not yet implemented.

---

## 5. Standard Mode

Used when a request carries a query, `compound_ids`, or `buckets` and no tags. Implemented inline in `radialDistill()` + `finalizeDistillation()`.

1. **Collect:** query the **`molecules`** table (filtered by `compound_ids` or joined via atom `buckets`), read each unique source file **once** into a content/mtime cache, and extract **semantic blocks** split on markdown headings (`extractSemanticBlocks`).
2. **Enrich:** each block becomes a **Decision Record** — structured JSON with `title`, `problem`/`solution`/`rationale`, `status` (active/deprecated/archived), `timestamps`, `provenance`, `tags`, and inferred `memory_type`. Digital-object + chat-session metadata are extracted alongside.
3. **Deduplicate:** block-level SimHash (`<block.type>:<simhash>` key) removes near-duplicate semantics across sources.
4. **Temporal preservation:** timestamps come from the source file's mtime, not batch time.

Compression is typically 5:1–10:1 (lower than line-level) but with far higher semantic coherence.

---

## 6. Tag-Based Mode

Same extraction as standard mode, filtered to a concept via `seed.tags` / `seed.buckets`. Implemented in `tagBasedDistill()` + `finalizeDistillation()`.

- **Query strategies:** single tag, multiple tags (OR logic), or all tags (full-corpus export organized by concept).
- **Cross-tag dedup:** each unique atom is processed exactly once regardless of how many tags it has — prevents memory bloat and keeps identical content to one Decision Record.
- Returns both structured Decision Records and `inflated_content` (raw atom text + tags) for downstream knowledge-graph construction or semantic indexing.

---

## 7. Legacy Line-Level Mode (legacy)

Implemented in `radial-distiller.ts` and reached only through the streaming path (`streaming-distiller.ts`). Retained for backward compatibility; **new work should use standard or full-corpus mode.**

- Three-phase pipeline: **COLLECT** (radially inflate all compounds) → **DEDUPLICATE** (line-hash index, strict/lenient normalization) → **REASSEMBLE** (coherent output compounds).
- Strict mode normalizes Unicode/case/whitespace and strips common prefixes; lenient mode trims only.
- Superseded by the block-level (standard) and compound-content-level (full-corpus) dedup methods above.

---

## 8. Self-Contamination Prevention

Prevents distillation outputs from being re-ingested as raw corpus (infinite recursion / polluted provenance). Two layers:

1. **Filename patterns** (`isDistillationOutput()`, `radial-distiller-v2.ts:46`): files matching `distilled_*`, `MASTER_DISTILLED_*`, or `*_distilled_*` with `.yaml/.json/.md` extensions are excluded from ingestion.
2. **Directory-level:** the watchdog ignores the `distills` directory (plus `distilled`, `synonym-ring`) — see `watchdog.ts`.

**Open edge case:** a renamed distilled file moved *outside* the distills dir could be ingested as raw content. Content-hash / provenance-chain validation is proposed but not yet implemented (§4 of the original Standard 028).

---

## 9. Output Storage & Format

- **Location:** `DISTILLS_DIR` (default `<data>/distills`, configurable via env `DISTILLS_DIR` or `paths.distills`). Kept separate from `mirrored_brain/`, which holds raw source as pointers only (Standard 021).
- **Formats:** `yaml` | `json` | `decision-records` | `json-full` | `nested-yaml`. Written when `output_path` is set or `auto_save` is true.
- **Pointer-only:** the `distills` table stores a metadata pointer to the output file, never the content itself.

---

## 10. Performance Notes

- **Memory-flat:** full-corpus keeps only hashes + tiny metadata in RAM during dedup and re-inflates survivors from disk at stream time — no full content held across passes (flat memory per Standard 012).
- **Read-once:** standard mode reads each unique source file exactly once via the content cache.
- **Metrics to track:** `totalAtoms`, `successfulReads`, `provenanceMismatches`, `fallbackReads`, `failedReads`, `skippedByContent` (see `DistillationMetrics`).

---

## 11. API Contract

**Request (`RadialDistillRequest`)** — key fields:

| Field | Type | Purpose |
|---|---|---|
| `mode` | `'standard' \| 'tag-based' \| 'full-corpus'` | selects method (§2) |
| `seed.query` | string | semantic seed for standard mode |
| `seed.compound_ids` | string[] | restrict to specific compounds (molecules.compound_id, **not** the mol_ PK) |
| `seed.buckets` | string[] | filter by tag buckets |
| `seed.tags` | string[] | tag-based selection (§6) |
| `inflate_radius` | number | full-corpus context window (default 500) |
| `simhash_hamming_threshold` | number | full-corpus dedup sensitivity (default 3) |
| `page_size`, `max_record_bytes` | number | full-corpus paging / record cap |
| `output_format` | string | output shape (§9) |
| `output_path`, `auto_save`, `export_to_inbox` | — | where/whether to write |
| `dry_run` | boolean | preview without writing |

**Response (`RadialDistillResult`):** `stats` (compounds_processed, blocks_total/unique, decision_records, compression_ratio, duration_ms, memory_peak_mb), `output` (format, path, size_bytes, records_created), `provenance` (source_compounds, distilled_at, parameters), plus `records` / `enriched_records` / `digital_objects` / `session_index` / `inflated_content` as relevant to the mode.

---

## 12. Testing Checklist

- [ ] Seedless request produces full-corpus output (JSONL + inline `dedup_of`).
- [ ] Triple+ identical compounds collapse to ONE survivor with a complete `dedup_of` chain; distinct compounds survive.
- [ ] Standard mode yields Decision Records with mtime-based timestamps and valid provenance.
- [ ] Tag-based mode dedups across tags (each unique atom once) and honors OR logic.
- [ ] No `distilled_*` output is re-ingested (filename + directory protection).
- [ ] `tsc --noEmit` green; distiller suite passes (`radial-distiller-grouping.test.ts` + full-corpus integration test).

---

**Related:** Standard 021 (Pointer-Only Storage), Standard 012 (Flat Memory), spec.md §Data Model.
