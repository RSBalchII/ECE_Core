# Standard 008: Radial Distillation — Lossless Corpus Compression

**Status:** 🚧 DRAFT | **Version:** 1.0 | **Date:** 2026-03-09
**Introduced:** v4.5.5 | **Supersedes:** Legacy distill.ts (naive atom-level compression)
**Component:** Engine / Distillation Service

---

## Philosophy Alignment

This standard embodies two core principles from the Anchor Engine philosophy:

> **"Forgetting is a feature, not a bug"** - The brain forgets constantly, leaving only what matters. Radial distillation deliberately removes redundancy, preserving unique facts while letting noise fade.

> **"Clarity through distillation, not accumulation"** - As you add more data, human memory doesn't get cluttered—it builds higher‑level abstractions. Each distillation pass makes the signal clearer, extracting the *why* behind decisions.

Radial distillation is not just compression—it's **deliberate forgetting** as a design principle. By removing redundancy across the entire corpus, we create a knowledge graph that becomes *more* precise over time, not less.

---

## 1. Executive Summary

Define the **Radial Distillation** architecture for creating near-lossless, deduplicated corpus compressions. Unlike the legacy distiller (which compressed individual atoms), radial distillation:

1. **Radially inflates** all main nodes to capture full context windows
2. **Deduplicates at the line/paragraph level** across the entire corpus
3. **Re-assembles** into coherent compounds with zero redundant content
4. **Respects mobile memory constraints** via streaming processing

**Result:** A distilled corpus where no line of text appears twice, preserving all unique information in a fraction of the space.

---

## 2. Core Problem & Resolution

### The Issue (Legacy Distiller)

The previous `distill.ts` implementation:
- **Atom-level only**: Queried atoms directly without radial inflation
- **Filtered content**: Excluded atoms with `source_path = 'atom_source'` (tag atoms)
- **No cross-atom dedup**: Each atom compressed independently
- **Lost context**: No surrounding context from `mirrored_brain/`

**Result:** 0 distilled nodes when all atoms were tag entries, or fragmented content without narrative coherence.

### The Resolution (Standard 008)

Radial distillation treats the corpus as a **content graph** rather than an atom table:

```
┌─────────────────────────────────────────────────────────────┐
│                    RADIAL DISTILLATION                       │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: COLLECT                                            │
│  ├── Traverse all compound hubs (mem_*)                      │
│  ├── Radially inflate each via ContextInflator               │
│  └── Build content window index (streaming)                  │
│                                                              │
│  Phase 2: DEDUPLICATE                                        │
│  ├── Normalize each line (whitespace, case)                  │
│  ├── Hash-based duplicate detection (SHA-256)                │
│  └── Build unique line index with provenance                 │
│                                                              │
│  Phase 3: REASSEMBLE                                         │
│  ├── Group unique lines by source proximity                  │
│  ├── Reconstruct coherent passages                           │
│  └── Write distilled compounds to mirrored_brain/            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Architecture

### 3.1. Three-Phase Pipeline

| Phase | Purpose | Memory Strategy |
|-------|---------|-----------------|
| **Collect** | Gather all content with radial inflation | Streaming: process compounds one at a time |
| **Deduplicate** | Find unique lines across corpus | Bounded: hash index with LRU eviction |
| **Reassemble** | Build coherent output compounds | Chunked: write in batches |

### 3.2. Radial Inflation Strategy

Each compound is inflated using **ContextInflator** with adaptive radius:

```typescript
// For distillation, use larger radius to capture full context
const inflationConfig = {
  baseRadius: 2000,        // 2KB window (vs 200-500 for search)
  maxRadius: 10000,        // 10KB cap per compound
  progressive: false,      // Uniform radius for all
  source: 'mirrored_brain' // Read from disk, not DB
};
```

**Why larger radius?**
- Search: Need quick, relevant snippets
- Distillation: Need complete context to detect cross-compound duplicates

### 3.3. Line-Level Deduplication

**Normalization (before hashing):**
1. Trim whitespace
2. Collapse multiple spaces
3. Lowercase (optional, configurable)
4. Remove common boilerplate (timestamps, "User:", "Assistant:")

**Duplicate Detection:**
```typescript
const lineHash = crypto.createHash('sha256')
  .update(normalizedLine)
  .digest('hex');

if (!uniqueLines.has(lineHash)) {
  uniqueLines.set(lineHash, {
    content: originalLine,
    provenance: [compoundId],
    firstSeen: timestamp
  });
}
```

### 3.4. Memory-Constrained Processing

For mobile/limited RAM environments (Termux, Raspberry Pi):

| Constraint | Solution |
|------------|----------|
| < 1GB RAM | Stream compounds, don't hold all in memory |
| Large corpora (>100MB) | External merge sort for deduplication |
| PGlite WASM limits | Chunk queries at PGLITE_CHUNK_IDS=100 |
| Disk space | Write incremental distilled chunks |

**Streaming Algorithm:**
```
FOR each compound IN corpus (ordered by timestamp):
  content = ContextInflator.inflate(compound, radius=2000)
  lines = content.split('\n')
  
  FOR each line IN lines:
    hash = normalizeAndHash(line)
    IF hash NOT IN globalDedupIndex:
      globalDedupIndex.add(hash)
      writeToIncrementalOutput(line, compound.id)
  
  // Force GC every N compounds
  IF compoundCount % 10 == 0:
    global.gc()
```

---

## 4. Implementation

### 4.1. File Structure

| File | Role |
|------|------|
| `engine/src/services/distillation/radial-distiller.ts` | Core three-phase pipeline |
| `engine/src/services/distillation/line-deduper.ts` | Hash-based line deduplication |
| `engine/src/services/distillation/streaming-writer.ts` | Incremental output writer |
| `engine/src/routes/v1/memory.ts` | POST /v1/memory/distill endpoint |
| `engine/src/commands/distill.ts` | CLI interface (updated) |

### 4.2. API Contract

#### Request

```typescript
interface RadialDistillRequest {
  // Scope
  seed?: {
    query?: string;           // Distill matching compounds only
    compound_ids?: string[];  // Explicit compound IDs
    buckets?: string[];       // Limit to buckets
  };
  
  // Inflation
  radius?: number;            // Base inflation radius (default: 2000)
  max_radius?: number;        // Hard cap (default: 10000)
  
  // Deduplication
  normalization?: 'strict' | 'lenient';  // strict = lowercase, trim, collapse
  preserve_formatting?: boolean;         // Keep original whitespace
  
  // Memory
  streaming?: boolean;        // Force streaming mode (default: auto)
  chunk_size?: number;        // Compounds per GC cycle (default: 10)
  
  // Output
  output_format?: 'yaml' | 'json' | 'compound';  // compound = write to mirrored_brain/
  output_path?: string;       // Custom output path
  export_to_inbox?: boolean;  // Also write to inbox/distilled/
}
```

#### Response

```typescript
interface RadialDistillResult {
  stats: {
    compounds_processed: number;
    lines_total: number;
    lines_unique: number;
    lines_duplicate: number;
    compression_ratio: string;  // "X.XX:1"
    duration_ms: number;
    memory_peak_mb: number;
  };
  output: {
    format: string;
    path?: string;
    size_bytes: number;
    compounds_created: number;
  };
  provenance: {
    source_compounds: string[];
    distilled_at: string;
    parameters: RadialDistillRequest;
  };
}
```

### 4.3. Key Functions

| Function | Phase | Purpose |
|----------|-------|---------|
| `collectCompounds()` | Collect | Stream compounds from DB with optional filtering |
| `inflateRadial()` | Collect | ContextInflator wrapper with distillation config |
| `normalizeLine()` | Deduplicate | Text normalization for hashing |
| `streamingDedup()` | Deduplicate | Bounded-memory duplicate detection |
| `reassembleCompounds()` | Reassemble | Group lines into coherent output files |
| `writeIncremental()` | Reassemble | Streaming output writer with backpressure |

---

## 5. Memory Management

### 5.1. Auto-Detection

```typescript
function detectMemoryMode(): 'streaming' | 'memory' {
  const totalMem = require('os').totalmem();
  const freeMem = require('os').freemem();
  
  // Force streaming if < 2GB total or < 500MB free
  if (totalMem < 2 * 1024 * 1024 * 1024 || freeMem < 500 * 1024 * 1024) {
    return 'streaming';
  }
  return 'memory';
}
```

### 5.2. Streaming Mode

In streaming mode:
- **No global line index**: Use external RocksDB/SQLite for dedup
- **Incremental output**: Write to temp files, merge at end
- **Aggressive GC**: `global.gc()` every N compounds
- **Bounded concurrency**: Process 1 compound at a time

### 5.3. Memory Mode

In memory mode (servers, desktops):
- **In-memory hash index**: Fastest deduplication
- **Batch output**: Collect all, then write
- **Parallel inflation**: Process compounds concurrently

---

## 6. Deduplication Strategies

### 6.1. Strict Mode (Default)

For maximum compression:
- Normalize Unicode
- Lowercase
- Collapse whitespace
- Remove common prefixes ("User:", "Assistant:", timestamps)

### 6.2. Lenient Mode

For preserving formatting:
- Trim only
- Preserve case
- Keep original spacing

### 6.3. Semantic Mode (Future)

For near-duplicate detection:
- SimHash comparison
- Allow minor variations
- Configurable similarity threshold

---

## 7. Output Formats

### 7.1. Compound Format (Default)

Writes to `mirrored_brain/distilled/`:

```
mirrored_brain/
├── distilled/
│   ├── batch_001.md
│   ├── batch_002.md
│   └── ...
```

Each file contains reassembled, deduplicated content ready for re-ingestion.

### 7.2. YAML Format

Structured output for analysis:

```yaml
metadata:
  source: "Radial Distillation"
  stats:
    compression_ratio: "12.5:1"
    lines_unique: 45000
    lines_total: 562500

content:
  - source: "mem_abc123"
    lines:
      - "Original line content"
      - "More unique content"
    provenance:
      - "mem_original_001"
      - "mem_original_042"
```

---

## 8. Integration

### 8.1. CLI Usage

```bash
# Distill entire corpus
node src/commands/distill.ts --radial

# Distill with custom radius
node src/commands/distill.ts --radial --radius 5000

# Force streaming mode (mobile)
node src/commands/distill.ts --radial --streaming

# Export to inbox
node src/commands/distill.ts --radial --export
```

### 8.2. API Usage

```bash
# Distill all chat history
POST /v1/memory/distill
{
  "seed": { "buckets": ["chat"] },
  "radius": 2000,
  "normalization": "strict",
  "streaming": true,
  "export_to_inbox": true
}
```

### 8.3. UI Integration

New prefix: `distill:`

| Prefix | Behavior |
|--------|----------|
| `distill:` | Radial distillation of entire corpus |
| `distill: <query>` | Distill matching compounds only |

---

## 9. Performance Targets

| Corpus Size | Mode | Duration | Memory | Compression |
|-------------|------|----------|--------|-------------|
| 10MB | Memory | ~30s | < 500MB | 8-15:1 |
| 100MB | Streaming | ~5min | < 300MB | 10-20:1 |
| 1GB | Streaming | ~45min | < 400MB | 15-30:1 |

**Note:** Compression ratio depends on corpus redundancy. Chat logs typically achieve 10-20:1.

---

## 10. Related Standards

- **Standard 104:** Universal Semantic Search — search algorithm
- **Standard 110:** Ephemeral Index — disposable database pattern
- **Standard 116:** Phoenix Protocol — mirrored_brain architecture
- **Standard 126:** Pointer-Only Index — byte-offset storage
- **Standard 009:** Illuminate BFS — graph traversal

---

## 11. Migration Guide

### From Legacy Distiller

1. Replace `distill.ts` imports with new radial distiller
2. Update API calls to use `RadialDistillRequest` interface
3. Enable streaming mode for mobile deployments
4. Update CLI to support `--radial` flag

### Database Compatibility

- No schema changes required
- Works with existing `atoms`, `molecules`, `compounds` tables
- Reads from `mirrored_brain/` (Standard 116)

---

**Introduced:** v4.5.5
**Owner:** Anchor Engine Team
**Status:** DRAFT — Pending Implementation
