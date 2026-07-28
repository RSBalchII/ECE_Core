# Standard 027: Distillation Output Storage — Purpose and Location

**Status:** ✅ IMPLEMENTED | **Version:** 1.0 | **Date:** 2026-05-19
**Introduced:** v4.x.x | **Supersedes:** None (clarification standard)
**Component:** Engine / Distillation Service / Storage Architecture
**Priority:** P0 — Fundamental architecture clarification

---

## Philosophy Alignment

This standard embodies the core principle:

> **"Derived summaries are not source material"** - Distillation outputs serve a different purpose than raw corpus files. They are compressed knowledge maps, not original content to be re-ingested.

> **"Separation of concerns in storage"** - Raw source files (pointer-only per Standard 021) and derived summaries (distillation outputs) should live separately to maintain clear architectural boundaries.

---

## 1. Executive Summary

Distillation outputs are **compressed knowledge maps** — event chains and nodal maps extracted from a data corpus, meant to seed the next conversation with FULL context of past conversations (plural). They are NOT raw content to be reintroduced into the source corpus.

**Key Distinctions:**
- **Raw corpus files**: Original source material stored as pointers in `mirrored_brain/` (Standard 021)
- **Distillation outputs**: Derived summaries stored separately in `notebook/distills/` for LLM consumption and context seeding

---

## 2. What Distillation Outputs ARE

### Definition

Distillation outputs are:
1. **Event chains/nodal maps** of conversations from a data corpus
2. **Compressed knowledge summaries** meant to seed the next conversation with FULL context of past conversations (plural)
3. A **"time/meaning map"** of the past, massively reduced in size from original corpus

### Characteristics

| Property | Description |
|----------|-------------|
| **Format** | Structured JSON or YAML decision records |
| **Content** | Problems, solutions, rationale, provenance metadata |
| **Size** | Typically 5:1 to 20:1 compression ratio vs raw corpus |
| **Purpose** | LLM consumption for context seeding |
| **Temporal** | Preserves temporal ordering via file mtime |

### Use Case Example

```
User has 100MB of chat workflow corpus (50+ YAML conversation files)
↓
Distilled down to ~500k tokens from tens of MBs of text
↓
Used as seed for new conversations/work-tasks with compressed knowledge
```

**Workflow:**
1. User ingests 100MB of historical chat logs into `mirrored_brain/` (pointer-only)
2. Runs radial distillation to extract decision records and semantic blocks
3. Distilled output (~500k tokens) stored in `notebook/distills/`
4. New conversation seeds on distilled output for instant context awareness
5. No need to re-ingest entire 100MB corpus

---

## 3. What Distillation Outputs ARE NOT

### Critical Clarifications

| Misconception | Reality |
|---------------|---------|
| "Distilled content should be added back to source corpus" | ❌ They are derived summaries, not original source material |
| "Distillation is just compression for storage efficiency" | ❌ It's semantic extraction for LLM consumption |
| "Distilled files can replace raw corpus in mirrored_brain/" | ❌ Raw corpus must remain (pointer-only per Standard 021) |
| "Distillation outputs are intermediate processing artifacts" | ❌ They are permanent knowledge maps, not temp files |

### Self-Contamination Prevention

**Problem:** If distillation outputs were re-ingested as raw content:
- Infinite recursion in the corpus
- Polluted provenance chains
- Loss of semantic distinction between source and derived

**Solution:** Distillation outputs are **excluded from ingestion**:
```typescript
// In atomizer/watchdog
const DISTILLATION_OUTPUT_PATTERNS = /(^|[\/\\])\..*|distilled_.*\.yaml$|MASTER_DISTILLED_.*\.yaml$|_distilled_.*\.(yaml|json|md)$/;

function isDistillationOutput(filePath: string): boolean {
  return DISTILLATION_OUTPUT_PATTERNS.some(pattern => pattern.test(path.basename(filePath)));
}
```

---

## 4. Storage Location

### Correct Path: `notebook/distills/`

The path `notebook/distills/` is **intentional and correct** because:

1. These are **derived summaries**, not raw source files
2. Raw source files follow pointer-only (Standard 021) in `mirrored_brain/`
3. Distillation outputs serve a different purpose — LLM consumption and context seeding

### Storage Structure

```
notebook/
└── distills/
    ├── batch_2026-05-19.json      # Decision records by date
    ├── standards_archive.json     # Standards corpus distilled
    └── chat_history_2026.json     # Chat logs distilled
```

### Comparison: Raw vs Derived Storage

| Location | Content Type | Purpose | Format |
|----------|-------------|---------|--------|
| `mirrored_brain/` | Raw source files (pointers) | Original corpus storage | Pointer references only |
| `notebook/distills/` | Distillation outputs | LLM context seeding | Structured JSON/YAML decision records |

---

## 5. Purpose and Use Cases

### Primary Purposes

1. **Compressed knowledge maps for LLM consumption**
   - Enable efficient context seeding without re-ingesting entire corpus
   - Provide temporal/semantic overview of past work

2. **Context inheritance across sessions**
   - New conversations can seed on distilled outputs
   - Instant awareness of historical decisions and patterns

3. **Knowledge graph foundation**
   - Event chains serve as nodes in semantic graphs
   - Provenance metadata enables traceability

### Use Case Examples

#### Example 1: Project Onboarding

```
Scenario: New developer joins project with 50+ standards documents

Without distillation:
- Must read all 50 standards manually (~2 hours)
- Or re-ingest entire corpus into new session

With distillation:
- Seed new conversation on notebook/distills/standards_archive.json
- LLM has instant context of all decisions, problems, solutions
- Onboarding time reduced to minutes
```

#### Example 2: Pattern Analysis

```
Scenario: Analyze decision patterns across project history

Distilled outputs provide:
- Structured access to problem/solution pairs
- Temporal ordering via timestamps
- Provenance for tracing decisions back to source files
```

#### Example 3: Corpus Compression Pipeline

```
100MB chat corpus → Distillation → ~500k tokens
↓
Seeds new conversation with full historical context
↓
No need to re-ingest original corpus
```

---

## 6. Implementation Details

### File Naming Convention

| Pattern | Description | Example |
|---------|-------------|---------|
| `batch_{YYYY-MM-DD}.json` | Daily distillation batches | `batch_2026-05-19.json` |
| `{source}_distilled.json` | Source-specific outputs | `standards_archive_distilled.json` |
| `MASTER_DISTILLED_{YYYY-MM-DD}.json` | Full corpus master | `MASTER_DISTILLED_2026-05-19.json` |

### Output Schema (Decision Records)

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

interface DistillationOutput {
  metadata: {
    source: "Radial Distillation v2.0";
    stats: {
      compression_ratio: string;
      records_total: number;
      records_unique: number;
      duration_ms: number;
    };
  };
  records: DecisionRecord[];
}
```

### API Integration

**Endpoint:** `POST /v1/memory/distill`

**Response includes output location:**
```typescript
{
  "output": {
    "format": "decision-records",
    "path": "notebook/distills/batch_2026-05-19.json",
    "size_bytes": 45000,
    "records_created": 127
  }
}
```

---

## 7. Testing

### Test Commands

```bash
# Distill and verify output location
node engine/dist/commands/distill.ts \
  --seed "specs/archive-standards" \
  --format decision-records \
  --output notebook/distills/test_distillation.json

# Verify file exists in correct location
ls -la notebook/distills/test_distillation.json

# Verify no self-contamination (no distilled_ references)
grep "distilled_" notebook/distills/test_distillation.json  # Should return nothing
```

### Verification Checklist

- [ ] Output files exist in `notebook/distills/` directory
- [ ] No files written to `mirrored_brain/` as raw content
- [ ] Decision records contain valid schema (id, title, problem/solution/rationale)
- [ ] Timestamps from file mtime (not batch time)
- [ ] Provenance arrays list source files correctly
- [ ] No self-contamination (no `distilled_` patterns in output)

---

## 8. Related Standards

| Standard | Relationship |
|----------|--------------|
| **Standard 021:** Pointer-Only Storage | Raw corpus must be pointers only in `mirrored_brain/`; distillation outputs are separate derived summaries |
| **Standard 008:** Radial Distillation v1.0 (legacy) | Original line-level distillation; superseded by v2.0 decision records |
| **Standard 010:** Radial Distillation v2.0 | Defines the semantic block extraction and decision record format used in this standard |
| **Standard 030:** Search Algorithm Testing Methodology | Distilled outputs can be used as seed corpus for testing search algorithms |

---

## 9. Migration Notes

### From Legacy Storage Patterns

If previously storing distillation outputs in `mirrored_brain/`:

1. Move files to `notebook/distills/`
2. Update any references in code/config
3. Ensure ingestion excludes `notebook/distills/` directory
4. Verify provenance chains are not polluted

### Backward Compatibility

- Legacy YAML output still available via `output_format: 'yaml'`
- Decision records format is new default (`decision-records`)
- Existing workflows can continue using legacy format during transition

---

## 10. Performance Considerations

| Corpus Size | Distilled Output Size | Compression Ratio | Use Case |
|-------------|----------------------|-------------------|----------|
| 10MB (50 standards) | ~2MB JSON | 5:1 | Quick context seeding |
| 100MB (500 standards) | ~15MB JSON | 7:1 | Project onboarding |
| 1GB (5000 standards) | ~80MB JSON | 13:1 | Full corpus knowledge map |

**Note:** Distillation outputs are smaller than raw text but larger than pointer-only storage. This is intentional — they preserve semantic meaning for LLM consumption, not just byte-level compression.

---

## 11. Future Considerations

### Potential Enhancements

- **Incremental distillation**: Update only changed sections
- **Multi-format outputs**: JSON + YAML + Markdown variants
- **Semantic search index**: Pre-computed indices on distilled content
- **Temporal decay weighting**: Older decisions weighted less in context windows

---

**Introduced:** v4.x.x  
**Owner:** Anchor Engine Team  
**Status:** ✅ IMPLEMENTED
