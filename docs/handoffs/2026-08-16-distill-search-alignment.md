# HANDOFF — Distiller ⇄ Search Alignment + Seedless Full-Corpus Distillation
Session handoff for resuming in a fresh session. Written 2026-08-16.
Workspace: /home/rsbiiw/workspace/anchor-engine-node

---

## 1. MISSION (north star, from the user)
- "Align the distiller with the way search works." Search's architecture: **atoms are POINTERS** — DB stores entity labels + byte coordinates; content lives ONLY in mirrored files on disk. The distiller must follow the same pointer discipline.
- Distillation = expand and dedupe **EVERY possible unique atom** (no seed query). Preferred mode: **seedless full-corpus distill**, triggered with empty body `POST /v1/distills/trigger` `{}` or `"mode":"full-corpus"`.

## 2. STATE AT HANDOFF — DONE & VERIFIED
1. **Seedless full-corpus pipeline works end-to-end** (real run, coding-notes data):
   - Ingest via watchdog: 12 atoms / 4 sources / 7 molecules.
   - `POST /v1/distills/trigger` `{}` → HTTP 200 (~5 ms), **12 total → 5 unique atoms (2.4:1 dedup)**.
   - Output streamed to `/home/rsbiiw/.anchor/distills/distilled_fullcorpus_*.jsonl`; all lines valid JSONL; `content_inflated:true` on 4/5 records (the `atom_source` row has no mirror file → correctly flagged false).
   - Distill checkpoint recorded in DB, visible via `/v1/distills/list`.
2. **Bug fixed**: `/v1/distills/list` crashed — `parameters JSONB` column comes back from PGlite as an already-parsed object, but all three read paths called `JSON.parse(row.parameters)` → `"[object Object]" is not valid JSON`. Fixed with tolerant helper `parseJsonField()` in `distill-manager.ts`, applied to all 3 sites.
3. **Route wiring done**: `/v1/distills/trigger` passes through `mode, page_size, inflate_radius, max_record_bytes`; HTTP response carries counts + `output.path` only (never the record array — memory safety).

## 3. EXACT POINT WHERE WE STOPPED — THE OFFSET FIX (designed, NOT yet coded)
**Problem**: Inflation anchors in full-corpus pass 2 use each atom row's own `[start_byte, end_byte]`. But ingestion writes **0/0 for compound-level `mem_*` rows by design**, nulls for `atom_source` rows → those records get inflated from byte 0 of the file (wrong window on large real files). Molecule-level `mol_*` rows DO carry real ranges.

**How search solves this (the template to copy)**:
- Search finds positions via **`atom_positions`**: `(compound_id, atom_label, byte_offset)` where `byte_offset` = molecule midpoint, label = atom tag (e.g. `#doc`). `ContextInflator.inflateFromAtomPositions()` queries by label; file path resolved via compound/molecule cache + `getMirrorPath(path, provenance)`, then bounded read `[start − radius − 1000 … end + radius + 1000]` over-read → snap to sentence boundary (`snapToSentenceBoundary`) → content.

**Planned fix (design agreed in-session)**:
In `radialDistillFullCorpus` pass 1 (pointer-only page fetch), for each page batch-fetch real anchors per unique atom from two sources, never reading content from DB:
  a) the atom row's own `source_path + [start_byte,end_byte]` when valid/non-zero (`mol_*` rows);
  b) `atom_positions` matched by label (from the atom's `tags`) joined to a file path — for compound-level `mem_*` rows.
Pass 2 then inflates radius around each real anchor exactly like `ContextInflator.inflateFromPath` (mirror resolution with provenance fallback, over-read, optional sentence snap). Keep: keyset pagination, dedup by molecular_signature → simhash → id, streaming JSONL writes, bounded per-record bytes.

## 4. DATA FINDINGS (verified via snapshot dump of live DB)
Snapshot: `/tmp/db-snapshot-1786859147`. Inspect script: `engine/.tmp-inspect-db.mjs` — run `cd engine && node .tmp-inspect-db.mjs /tmp/db-snapshot-<ts>` (MUST live under engine/ for pnpm resolution; takes snapshot dir as arg). Its final "TAGS vs LABEL" query has a SQL bug (`column "x" does not exist`); main sections work.

**atoms table (12 rows)** — all `tags=['#doc']`, provenance internal:
| id | source_path | start/end bytes |
|---|---|---|
| mem_7fba… | deep-verify.md | 0 / 0 |
| mol_6103… | deep-verify.md | 0 – 31 |
| mol_d56b… | deep-verify.md | 32 – 48 |
| mem_fdfb… | smoke-test-1.md | 0 / 0 |
| mol_3d9f… | smoke-test-1.md | 0 – 389 |
| mem_f050… | smoke-verify.md | 0 / 0 |
| mol_bff9… | smoke-verify.md | 0 – 59 |
| mol_593c… | smoke-verify.md | 60 – 81 |
| atom_ab7… | `atom_source` (sentinel) | null / null |
| mem_d141… | unique-smoke-test.md | 0 / 0 |
| mol_befd… | unique-smoke-test.md | 0 – 72 |
| mol_6759… | unique-smoke-test.md | 73 – 87 |

**molecules (7 rows)**: same paths/ranges as the mol_* atoms; `compound_id` = hex ids (`61b4b05d…`).
**atom_positions (7 rows)**: `(mem_*, '#doc', midByte)` offsets 15, 40, 194, 29, 70, 36, 80 (= molecule midpoints).

## 5. FILE MAP — read locations to resume fast
### A. Code we're modifying
- `engine/src/services/distillation/radial-distiller-v2.ts` (1955 lines)
  - **L1578** `export async function radialDistillFullCorpus(request)` — seedless pipeline: pass 1 keyset-paginated pointer fetch + dedup; pass 2 per-unique-atom disk inflation streaming JSONL with backpressure.
  - **L1535** `readRangeFromMirror(...)` — current range reader (anchored at row bytes; to replace/augment).
  - **~L1095–1280** standard-mode mirror resolution + whole-file reads w/ provenance fallbacks.
  - **L158** `RadialDistillRequest` interface (mode, page_size, inflate_radius, max_record_bytes).
### B. Search template to align with
- `engine/src/services/search/context-inflator.ts` (884 lines)
  - **L34** `inflate()` — radius policy: base ≥200, top 10% ×2.0, next 40% ×1.5, cap 5000; adaptive-concurrency batching.
  - **L167** `snapToSentenceBoundary` — window snapping after read.
  - **L221 / L249** `inflateFromDisk` / `inflateFromPath` — THE inflation recipe: `getMirrorPath(path, provenance)` → fallback original path → over-read ±1000 lookahead → bounded `fd.read` → snap → text. Returns null if file missing (NO DB content fallback).
  - **L336** `getAtomLocations(term,…)` — atom_positions + molecules JOIN (`ON ap.compound_id = m.compound_id` — see open question OQ-1).
  - **L461** `inflateFromAtomPositions(searchTerm, radius,…)` — position lookup by label variants.
- `engine/src/services/search/search.ts` — `findAnchors` + `executeSearch` (anchor expansion → radial walk → 3-layer dedup).
### C. Ingestion facts (why offsets are what they are)
- `engine/src/services/ingest/ingest-atomic.ts` (494 lines)
  - **L313** `batchWriteMemory`: compound-level rows INSERTed with literal `0, 0` ("not applicable for compound-level atom entry" — by design); tags = all atom labels; molecule-level rows get real bytes.
  - **L417 / L447** `batchWriteAtomPositions` / flush: `(compound_id, atom_label=atom label, byte_offset=molecule midpoint)`, ON CONFLICT DO NOTHING.
### D. Schema / infra
- `engine/src/core/db.ts` — init ~L89–150 (`PGLITE_DB_PATH || pathManager.getDatabasePath()`, wipe_on_startup). Grep `'CREATE TABLE IF NOT EXISTS distills'` for distills table (parameters is **JSONB**). atom_positions: `(compound_id, atom_label, byte_offset)`. Atoms has NO label column — labels live in `tags[]` and atom_positions.
- `engine/src/config/paths.ts` — L72–76 CONTEXT_DATA_DIR default `~/.anchor/context_data`; **L102** `PATHS.DISTILLS_DIR` = `~/.anchor/distills`.
- `engine/src/services/distillation/distill-manager.ts` — `parseJsonField()` helper (~L55–80, added this session) + 3 fixed read sites; `recordDistill` inserts `JSON.stringify(parameters)` (fine for JSONB).
- `~/.anchor/user_settings.json` — port **3160**, api_key present, `database.wipe_on_startup: true`.

## 6. OPERATIONAL RUNBOOK (verified this session)
```bash
# Typecheck + build
cd /home/rsbiiw/workspace/anchor-engine-node/engine && npx tsc --noEmit
cd /home/rsbiiw/workspace/anchor-engine-node && pnpm run build

# Restart server (wipe_on_startup=true → DB wiped on every start!)
pgrep -f "dist/index.js"            # get PID; kill -9 <pid>
#   NEVER `pkill -f` with broad patterns — matched our own shell once (exit -9)
# background, workdir = project root:  node --expose-gc engine/dist/index.js

# Ingest test data (after EVERY restart)
curl -s -X POST http://localhost:3160/v1/watchdog/start \
  -H "Content-Type: application/json" \
  -d '{"paths":["/home/rsbiiw/workspace/coding-notes"],"recursive":true}'
# wait ~25 s → curl -s http://localhost:3160/v1/stats   # expect atoms:12 sources:4 molecules:7

# Seedless distill + inspect
curl -s -X POST http://localhost:3160/v1/distills/trigger -H "Content-Type: application/json" -d '{}'
F=$(ls -t /home/rsbiiw/.anchor/distills/distilled_fullcorpus_*.jsonl | head -1)

# Inspect DB directly? SNAPSHOT FIRST (live dir wipes on restart):
cp -a /home/rsbiiw/.anchor/context_data /tmp/db-snapshot-$(date +%s)
cd engine && node .tmp-inspect-db.mjs /tmp/db-snapshot-<ts>

# Server won't start (missing API key)? → cd project root && node setup-user-config.mjs
```
Gotchas: ESM imports of `@electric-sql/pglite` fail from `/tmp` — scripts must live under `engine/`. Complex sed/grep shell one-liners can trip the command parser — prefer file tools.

## 7. UNRESOLVED / UNCLEAR LOGIC TO WORK THROUGH NEXT SESSION
**OQ-1 (BLOCKS the offset fix) — what does `atom_positions.compound_id` actually reference?**
Positions carry `compound_id = mem_*` ids, but `molecules.compound_id` holds hex ids → my snapshot LEFT JOIN returned `path: null` for all 7 position rows. Yet ingestion writes `batch.push(m.compoundId, label, midByte)` where `m.compoundId` should be the molecule's compound link… and search's own `getAtomLocations` joins `molecules ON ap.compound_id = m.compound_id`. If that join is broken for these rows, **search's path resolution has the same gap** (positions found but no file). Diagnostic to run on a fresh snapshot:
```sql
SELECT id, compound_id, source_path FROM molecules LIMIT 20;      -- what are molecule ids?
SELECT DISTINCT compound_id FROM atom_positions;                   -- mem_* confirmed
-- test both keys:
SELECT count(*) FROM atom_positions ap JOIN molecules m ON ap.compound_id = m.id;
SELECT count(*) FROM atom_positions ap JOIN molecules m ON ap.compound_id = m.compound_id;
```
Possibilities: (a) `molecules.id` IS the mem_* id and my dump misread columns; (b) positions reference a removed/legacy table; (c) ingestion's molecule path uses `compoundId` field differently than I assumed.

**OQ-2 — dedup key vs search identity.** Full-corpus dedups by `molecular_signature → simhash → id`. But in this dataset ALL 12 atoms share one tag set (`#doc`) and the compound-level rows carry the molecule signature as their simhash field… yet we got 5 unique. Need to confirm the 5 uniques map 1:1 to (a) 4 files' content + 1 sentinel, or (b) something else — i.e., is dedup collapsing across FILES where it shouldn't? Verify by comparing unique-atom source_path sets before/after offset fix on a multi-file corpus with repeated text.

**OQ-3 — `molecules` table vs removed `compounds`.** Standard 051 says compounds REMOVED; molecules is the live file table, but ingestion code still calls variables "compoundId" and atom rows have both an `id` (mem_/mol_) AND a `compound_id` column. The three-way identity (atom.id / atoms.compound_id / molecules.compound_id) is only partly documented — worth one pass to pin down which id is canonical for file lookups vs positions joins before writing the offset join.

**OQ-4 — sentence snapping in distill context.** Search snaps windows to sentence boundaries because a search hit is a keyword. For full-corpus records, do we want sentences (loses structural context) or raw bounded ranges (keeps whatever the radius catches)? Current code does raw ranges; decision needed before copying `snapToSentenceBoundary`.

**OQ-5 — sentinel `atom_source` rows.** One row per corpus with literal path `atom_source`, null bytes, no mirror file. Is this a real ingestion artifact (worth fixing at source) or an intentional placeholder? It currently produces a `content_inflated:false` record in every distill.

**DEFERRED (task 6, explicit user agreement — backend first):** `index.html` frontend to stream/view results from the created distillation files in `.anchor/distills/`, UI updating as the file is produced.

## 8. NEXT ACTIONS (ordered)
1. Resolve OQ-1/OQ-3 with snapshot diagnostics (§7).
2. Implement offset fix per §3 design; keep pointer-only discipline.
3. Rebuild → restart → re-ingest → seedless trigger → verify mol_*/mem_* records carry real non-zero anchors and correct file windows (compare against on-disk bytes).
4. Regression: `/v1/distills/list`, standard seed-based distill path still works.
5. Then OQ-2/OQ-4/OQ-5 decisions, then deferred frontend.

## 9. DESIGN RATIONALE TO PRESERVE
- Memory safety is a hard constraint: keyset pagination (page_size default 500), pointer-only pass 1, bounded reads (inflate_radius ≤1000, max_record_bytes default 8192), streaming writes with backpressure — the HTTP response must NEVER carry the record array.
- Dedup identity order: `molecular_signature` → simhash → id; duplicates merge into one unique atom with `occurrences[]`.
- "Aligned with search" means: same position source (atom_positions / row pointers), same path resolution (getMirrorPath + provenance fallback), same bounded-read shape. Do NOT invent a new content source, and NEVER read content from the DB in distillation.
