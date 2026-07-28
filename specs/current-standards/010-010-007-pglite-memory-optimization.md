# Standard 007: PGlite Memory Optimization

**Date:** March 6, 2026
**Status:** ✅ ACTIVE
**Authority:** OOM Prevention Sprint
**Domain:** Database, Performance, Embedded Deployment

---

## 1. Problem

PGlite's WASM runtime allocates a large internal buffer cache by default (~1GB `shared_buffers`).
On top of the wink-nlp model and application heap, this pushed the process past 6GB and caused
OOM crashes during concurrent searches on large corpora (215K+ atoms).

A secondary issue: previously, memory settings were applied via `SET` commands *after* PGlite
initialization. This was too late — the WASM allocator had already reserved the default buffers.

---

## 2. Solution

Pass memory settings directly to the `PGlite` constructor so the WASM allocator honors them
from the start. Also enable `relaxedDurability` to skip unnecessary `fsync` calls during
ingestion (see Standard 059 §11).

---

## 3. Implementation

**`engine/src/core/db.ts`** — PGlite initialization:

```typescript
this.dbInstance = await new PGlite(dbPath, {
  relaxedDurability: true,  // Skip fsync during ingestion (Standard 059)
  settings: {
    'shared_buffers':                 '256MB',  // Down from default ~1GB
    'effective_cache_size':           '512MB',  // Planner estimate cap
    'work_mem':                        '16MB',  // Per sort/hash in physics walker CTEs
    'maintenance_work_mem':            '64MB',  // VACUUM, CREATE INDEX
    'wal_buffers':                      '4MB',
    'checkpoint_completion_target':      0.9,   // Spread checkpoint writes
    'random_page_cost':                  1.1,   // Prefer seq scans (WASM has no disk)
    'seq_page_cost':                     1.0,
  }
});
```

---

## 4. Memory Budget (Corpus: 215K atoms, 26MB source)

| Component | Approx Heap | Notes |
|-----------|-------------|-------|
| wink-nlp NLP model | ~1.5–2 GB | Live V8 objects, not GC-able |
| PGlite WASM buffer | ~256 MB | `shared_buffers` (was ~1 GB) |
| Physics walker CTEs | ~16 MB × n | Per concurrent query (`work_mem`) |
| Application heap | ~200–400 MB | Search results, inflated snippets |
| **Total (idle)** | **~2.0–2.7 GB** | After ingestion + GC |
| **Peak (1 search)** | **~3.5–4 GB** | With serialization lock active |

`--max-old-space-size=6144` in `package.json` provides headroom for worst-case scenarios.

---

## 5. Interaction with OOM Prevention Stack

This standard is one layer of a three-layer OOM prevention strategy:

1. **Standard 007 (this)** — Reduce PGlite baseline memory consumption at init
2. **Search serialization lock** (`search.ts`) — Only 1 search runs at a time
3. **Memory pressure downgrade** (`search.ts`) — If `heapUsed > 3.2 GB`, downgrade
   `max-recall` strategy to `standard` before executing

All three are required. Removing any one layer risks OOM on large corpora.

---

## 6. `relaxedDurability` Trade-off

| Mode | Fsync behavior | Risk | Use case |
|------|---------------|------|----------|
| Default (`false`) | fsync on every WAL write | Slow ingestion | Production DB |
| `relaxedDurability: true` | No fsync | Data loss on power-off during write | **Ephemeral index** |

The engine's database is an ephemeral index (Standard 051, Standard 095). Data loss on
crash is acceptable — the source of truth is the filesystem (`mirrored_brain/`). The
speedup during large file ingestion is significant (~10-50x, per Standard 119).

---

## 7. Related Standards

- **Standard 051** — Ephemeral Index (database is disposable)
- **Standard 059** — Reliable Ingestion (§11 adds `relaxedDurability`)
- **Standard 095** — Database Reset on Startup
- **Standard 119** — PGlite-First Architecture

---

## 8. Do Not

- Do **not** set `shared_buffers` higher than 512MB — the wink-nlp model baseline leaves
  insufficient headroom for large values.
- Do **not** remove `relaxedDurability` unless the database is converted to a durable store
  (see Proposal 127: External PostgreSQL Migration).
- Do **not** apply memory settings via `SET` after init — the WASM allocator ignores them.

---

**Approved by:** OOM Prevention Sprint, March 2026
**Review Date:** September 2026 (or upon corpus size doubling)
