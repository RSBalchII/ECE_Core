# Full-Corpus Content-SimHash Dedup (dedup_of provenance)

Goal: finish transitioning full-corpus distillation to **content-meaning dedup** — hash each compound's real bytes with SimHash, keep the newest of every near-duplicate cluster, and record absorbed older versions as flat `dedup_of` provenance. Settled on inline `dedup_of` only (no manifest). Must stay memory-light: keep only hashes in RAM during dedup; re-inflate survivors from the mirror at stream time.

## Decisions (confirmed with user)
- **Provenance shape:** inline `dedup_of[]` on survivor records ONLY. Drop the `manifest` / `dedup_method` option entirely.
- **Dedup key:** SimHash of inflated compound CONTENT (via WASM fingerprint module), Hamming threshold default 3.
- **Memory model:** dedup pass keeps only hashes + tiny metadata in RAM; streaming re-reads each survivor's bounded window from disk. No full content held across passes (Standard 016 flat memory).
- **Chain collapse:** a third+ identical compound must absorb the WHOLE cluster, not escape because its immediate predecessor was already dropped.

## Steps
- [ ] 1. Remove `dedup_method` / manifest path from request interface, `distill.ts` CLI, and `v1/distills.ts` route; keep `simhash_hamming_threshold`.
- [ ] 2. Rewrite dedup pass in `radial-distiller-v2.ts`: hash each candidate's bounded window once, keep only hashes + metadata in RAM (discard content), union-find over record ids so matches resolve to the cluster ROOT survivor.
- [ ] 3. Fix broken chain collapse: when nearest seen is already absorbed, follow `survivorId` to its root survivor and fold that survivor's own `dedup_of` chain into the new survivor — never skip an already-dropped predecessor.
- [ ] 4. Rewrite stream pass to re-inflate each survivor from disk on demand (bounded window) and write inline `dedup_of` only when non-empty; drop manifest block.
- [ ] 5. Update `radial-distiller-grouping.test.ts`: give atoms distinct content so it measures contiguous per-file ordering independent of dedup (identical-content collapse is now intended behavior).
- [ ] 6. Add a new integration test asserting triple+ identical compounds collapse to ONE survivor with full `dedup_of` chain, and that distinct compounds survive.
- [ ] 7. Typecheck (`tsc --noEmit`) + run distiller suite; confirm all green.
- [ ] 8. (Follow-up) Empirically sweep `simhash_hamming_threshold` to measure dedup effectiveness / false-positive rate on a real mirror.

## Notes / gotchas
- `computeSimHash` uses WASM fingerprint module with SHA-256 crypto fallback; identical content → identical hash.
- Union-find `find()` path-compress over `survivorId`; `recordsById` maps id -> record for O(1) root lookup.
- Oldest-first sort (by timestamp, `?? Infinity`) so newer always absorbs older.
- `content_length` in `DedupReference` stays undefined at dedup time (provenance only); content is re-inflated at stream time.
- O(n^2) Hamming scan over hashes only — fine for current compound count; known ceiling noted, not fixed here.
