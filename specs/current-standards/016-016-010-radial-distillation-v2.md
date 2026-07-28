# Standard 133: Radial Distillation v2.0 — Decision Record Output

**Status:** ✅ IMPLEMENTED | **Version:** 2.0 | **Date:** 2026-03-14
**Introduced:** v4.8.0 | **Supersedes:** Standard 008 (Legacy line-level distillation)

---

## Philosophy Alignment

This standard embodies the core principle:

> **"Clarity through distillation, not accumulation"** - Human memory doesn't store every word; it stores the gist, the decisions, the *why*. Distillation v2.0 extracts Decision Records—structured captures of problems, solutions, and rationale—leaving behind the noise while preserving the signal.

Unlike v1 (line-level deduplication), v2.0 extracts **semantic meaning**—the decisions and reasoning that matter. This mirrors how human memory clarifies over time: details fade, but core truths strengthen.

---

## 1. Executive Summary

Radial Distillation v2.0 produces **Decision Records** — structured JSON objects capturing problems, solutions, rationale, and provenance — instead of line-level deduplicated text. This format is optimized for LLM consumption while preserving temporal and semantic information.

**Key Improvements:**
1. **Semantic Units:** Extracts sections by markdown headings, not lines
2. **Decision Records:** Structured JSON with problem/solution/rationale fields
3. **Self-Contamination Prevention:** Filters `distilled_*.yaml` files from ingestion (checks both filename and directory paths)
4. **Temporal Preservation:** Uses file mtime, not batch time
5. **Block-Level Deduplication:** SimHash on semantic blocks, not lines

**Note:** Phase 4 (semantic block extraction) is implemented in a separate utility module (`block-extractor.ts`) for better code organization and reusability.

---

## 2. Architecture

### 2.1 Three-Phase Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│              RADIAL DISTILLATION v2.0                        │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: COLLECT                                            │
│  ├── Filter distillation outputs (prevent self-contamination)│
│  ├── Extract semantic blocks by markdown headings           │
│  └── Tag blocks by type (problem, solution, rationale, etc.)│
│                                                              │
│  Phase 2: DEDUPLICATE                                        │
│  ├── Group blocks by type                                   │
│  ├── Compute SimHash per block                              │
│  └── Merge blocks with same type + hash (combine provenance)│
│                                                              │
│  Phase 3: REASSEMBLE                                         │
│  ├── Group blocks by source file                            │
│  ├── Assemble Decision Record JSON                          │
│  └── Write output (JSON or legacy YAML)                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Decision Record Schema

```typescript
interface DecisionRecord {
  id: string;               // e.g., "std-001"
  title: string;            // Full title from heading
  problem?: string;         // Problem description
  solution?: string[];      // Numbered requirements
  rationale?: string;       // Why this approach was chosen
  supersedes?: string[];    // IDs of deprecated standards
  status: "active" | "deprecated" | "archived";
  timestamp: string;        // ISO date from file mtime
  provenance: string[];     // Source file paths
  tags: string[];           // Extracted tags (#tag)
}
```

### 2.3 Example Output

```json
[
  {
    "id": "std-094",
    "title": "Standard 094: Smart Search Protocol",
    "problem": "The initial search engine relied solely on FTS, which was too rigid for natural language queries.",
    "solution": [
      "1. Implement intelligent query parsing to strip fluff (common verbs, articles).",
      "2. If FTS returns zero results, automatically fall back to fuzzy search."
    ],
    "rationale": "User queries often contain extra words; stripping them improves recall.",
    "supersedes": [],
    "status": "deprecated",
    "timestamp": "2025-09-10T14:23:00Z",
    "provenance": ["specs/standards/094-smart-search-protocol.md"],
    "tags": ["search", "fuzzy", "deprecated"]
  }
]
```

---

## 3. Implementation Details

### 3.1 Self-Contamination Prevention

**Problem:** Previous distillations were re-ingested, causing infinite recursion and polluted output.

**Solution:** Filter distillation outputs in watchdog and atomizer:

```typescript
// watchdog.ts
const IGNORE_PATTERNS = /(^|[\/\\])\..*|distilled_.*\.yaml$|MASTER_DISTILLED_.*\.yaml$|_distilled_.*\.(yaml|json|md)$/;

// radial-distiller-v2.ts
function isDistillationOutput(filePath: string): boolean {
  return DISTILLATION_OUTPUT_PATTERNS.some(pattern => pattern.test(path.basename(filePath)));
}
```

### 3.2 Semantic Block Extraction

**Algorithm:**
1. Split markdown on headings (`#`, `##`, `###`)
2. Detect block type from heading keywords:
   - `problem`, `issue`, `challenge` → `problem`
   - `solution`, `approach`, `implementation` → `solution`
   - `rationale`, `why`, `reason` → `rationale`
   - `status`, `state` → `status`
3. Compute SimHash per block
4. Preserve file mtime for temporal decay

### 3.3 Block-Level Deduplication

```typescript
// Group by type first, then deduplicate within type
const blocksByType = new Map<string, SemanticBlock[]>();
for (const block of allBlocks) {
  const key = `${block.type}:${block.simhash}`;
  // Merge provenance for duplicate blocks
}
```

**Compression Ratio:** Typically 5:1 to 10:1 (vs 15:1 to 30:1 for line-level)

**Trade-off:** Less compression, but **much higher semantic coherence**

### 3.4 Temporal Preservation

```typescript
// Use file mtime, not batch time
const stats = fs.statSync(localPath);
const mtime = stats.mtimeMs;

// In Decision Record
timestamp: new Date(earliestMtime).toISOString()
```

**Why:** STAR algorithm uses temporal decay — newer decisions have stronger gravity.

---

## 4. API Contract

### 4.1 Request

```typescript
POST /v1/memory/distill

{
  "seed": {
    "query?: string,           // Distill matching compounds only
    "compound_ids?: string[],  // Explicit compound IDs
    "buckets?: string[]        // Limit to buckets
  },
  "radius?: number,            // Inflation radius (default: 3)
  "output_format?: "yaml" | "json" | "decision-records",  // Default: decision-records
  "output_path?: string"       // Custom output path
}
```

### 4.2 Response

```typescript
{
  "stats": {
    "compounds_processed": number,
    "blocks_total": number,
    "blocks_unique": number,
    "decision_records": number,
    "compression_ratio": string,  // "X.X:1"
    "duration_ms": number,
    "memory_peak_mb": number
  },
  "output": {
    "format": string,
    "path": string,
    "size_bytes": number,
    "records_created": number
  },
  "provenance": {
    "source_compounds": string[],
    "distilled_at": string,
    "parameters": DistillRequest
  }
}
```

---

## 5. Usage Examples

### 5.1 Distill Standards Archive

```bash
# Via CLI
anchor distill --seed "specs/archive-standards" --format decision-records

# Via API
curl -X POST http://localhost:3160/v1/memory/distill \
  -H "Content-Type: application/json" \
  -d '{
    "seed": {"buckets": ["specs"]},
    "output_format": "decision-records"
  }'
```

### 5.2 Distill with Query

```bash
curl -X POST http://localhost:3160/v1/memory/distill \
  -d '{"seed": {"query": "search protocol"}, "radius": 3}'
```

### 5.3 Legacy YAML Output

```bash
curl -X POST http://localhost:3160/v1/memory/distill \
  -d '{"output_format": "yaml"}'
```

---

## 6. Testing

### 6.1 Test Commands

```bash
# Test on standards archive
node engine/dist/commands/distill.js \
  --seed "specs/archive-standards" \
  --format decision-records \
  --output specs/distilled_standards.json

# Verify no self-contamination
grep "distilled_" specs/distilled_standards.json  # Should return nothing
```

### 6.2 Verification Checklist

- [ ] No `distilled_` lines in output
- [ ] Each standard = 1+ Decision Records
- [ ] Timestamps from file mtime (not batch time)
- [ ] Provenance arrays list source files
- [ ] Status correctly detected (active/deprecated/archived)
- [ ] Tags extracted from content

---

## 7. Backward Compatibility

**Legacy YAML output** still available:

```typescript
output_format: 'yaml'  // Uses original line-level distiller
```

**Migration Path:**
1. Use `decision-records` for new distillations
2. Legacy YAML remains for existing workflows
3. Deprecate YAML in v5.0

---

## 8. Performance

| Corpus Size | Mode | Duration | Memory | Compression |
|-------------|------|----------|--------|-------------|
| 10MB (50 standards) | Decision Records | ~15s | < 300MB | 5:1 |
| 100MB (500 standards) | Decision Records | ~2min | < 400MB | 7:1 |
| 1GB (5000 standards) | Decision Records | ~15min | < 500MB | 8:1 |

**Note:** Compression ratio lower than line-level (15-30:1), but **semantic coherence much higher**

---

## 9. Related Standards

- **Standard 008:** Legacy Radial Distillation (line-level)
- **Standard 110:** Ephemeral Index (disposable database)
- **Standard 116:** Phoenix Protocol (mirrored_brain architecture)
- **Standard 126:** Pointer-Only Index

---

**Introduced:** v4.8.0
**Owner:** Anchor Engine Team
**Status:** ✅ IMPLEMENTED
