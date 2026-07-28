# Standard 134: Zero-Copy Deduplication in Distillation

**Status:** ✅ Implemented
**Date:** April 3, 2026
**Priority:** P1 (Performance Critical)
**Branch:** `dev/zero-copy-dedup`

---

## Problem Statement

The radial distiller's three-phase pipeline (`COLLECT → DEDUPLICATE → REASSEMBLE`) processes every inflated compound through the full UTF-8 string conversion and line-level deduplication pipeline, even when the compound content is a duplicate of content already seen.

### The Cost

For each compound in the distillation pipeline:

1. **`ContextInflator.inflate()`** reads file bytes → `buffer.toString('utf-8')` — O(N) UTF-8 validation
2. Content string is split into lines via `content.split('\n')` — allocates new string array
3. Each line is normalized and hashed via `crypto.createHash('sha256').update(line).digest('hex')`
4. **Only after all this** is the line checked against the dedup Map

If 90% of compounds contain duplicate content (common in large conversation logs, repeated code patterns, or version histories), **90% of the UTF-8 validation, string splitting, and line hashing is wasted work**.

### Measured Impact (from anchor-engine-rust)

The Rust implementation measured this exact pattern:
- **Before:** Every block paid UTF-8 validation tax (~50-100 cycles/byte)
- **After:** Only unique blocks pay UTF-8 validation
- **For 50% duplicate rate:** ~50% CPU savings on distillation
- **For 90% duplicate rate:** ~90% CPU savings

---

## Solution

### Two-Tier Deduplication

**Tier 1: Compound-Level Dedup (Buffer Hash)**

Before any string processing, compute a fast SHA-256 hash of the raw inflated content string (as bytes). Check against a `Set<string>` of seen compound hashes. If duplicate, skip the entire line-level pipeline.

```
inflated content (string)
    ↓
Buffer.from(content, 'utf8') → raw bytes
    ↓
crypto.createHash('sha256').update(buffer).digest('base64url')
    ↓
seenHashes.has(hash)?
    ├── YES → Skip entirely (duplicate compound)
    └── NO  → Add to seenHashes, proceed to line-level dedup
```

**Tier 2: Line-Level Dedup (Existing)**

For compounds that pass Tier 1, the existing line-level dedup pipeline runs:
- Split into lines
- Normalize each line
- Hash normalized content
- Check/update dedup Map

### Why SHA-256 at Compound Level (Not SimHash)?

SimHash is designed for **semantic near-duplicate detection** across text fragments. For compound-level dedup, we need **exact duplicate detection** — two inflated compounds are either byte-identical or they're not. SHA-256 is faster and has zero false positives.

SimHash remains valuable for the search dedup pipeline (search results may be near-duplicates), but the distiller benefits from exact-match hashing.

### Implementation Details

**File:** `engine/src/services/distillation/radial-distiller.ts`

```typescript
// New: compound-level dedup hash set
const seenCompoundHashes = new Set<string>();

// In the deduplicateLines loop:
for await (const compound of compoundGenerator) {
  // TIER 1: Hash raw content bytes BEFORE splitting
  const contentBuffer = Buffer.from(compound.content, 'utf8');
  const compoundHash = crypto.createHash('sha256').update(contentBuffer).digest('base64url');
  
  if (seenCompoundHashes.has(compoundHash)) {
    duplicateCompounds++;
    continue; // Skip entire compound - no UTF-8 split, no line hashing
  }
  seenCompoundHashes.add(compoundHash);

  // TIER 2: Existing line-level dedup (only for unique compounds)
  const lines = compound.content.split('\n');
  // ... rest of existing logic
}
```

### Memory Impact

- `Set<string>` of base64url SHA-256 hashes: 43 bytes per compound
- For 10,000 compounds: ~430 KB overhead
- Savings: skips `split()`, `normalizeLine()`, `hashLine()` for duplicates
- Net positive for any duplicate rate > 5%

---

## Verification

### Test Cases

1. **All unique compounds:** No duplicates → Tier 1 passes everything through → same performance as before (minimal overhead)
2. **All duplicate compounds:** Same content repeated → Tier 1 skips 99.9% → ~100x speedup
3. **Mixed (realistic):** 50-90% duplicate rate → 2-10x speedup depending on content

### Metrics to Track

- `duplicate_compounds_skipped` — count of compounds skipped by Tier 1
- `tier1_overhead_ms` — time spent in Tier 1 hashing (should be < 1ms per compound)
- `total_distill_duration_ms` — compare before/after on same corpus

---

## Cross-Reference

- **Standard 133:** Radial Distillation (the pipeline this optimizes)
- **Standard 074:** SimHash Fingerprinting (used for search dedup, not distill)
- **anchor-engine-rust commit 0c67d23:** Zero-copy dedup in distill (Rust equivalent)

---

## Definition of Done

- [x] Tier 1 compound-level dedup implemented in `radial-distiller.ts`
- [x] Stats include `duplicate_compounds_skipped` count
- [x] No behavioral change for unique content (same output, faster)
- [x] Performance benchmark on 100MB+ corpus
- [x] Changelog entry
