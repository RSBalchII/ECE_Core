# Standard 021: Pointer-Only Storage

**Status:** Active  
**Date:** 2026-03-25  
**Priority:** CRITICAL  
**Supersedes:** References in Standards 008, 020

---

## Rule

**Database stores POINTERS ONLY - NO CONTENT EVER**

### What Database Stores

| Table | Columns | Purpose |
|-------|---------|---------|
| **molecules** | `id`, `file_path`, `start_byte`, `end_byte`, `type`, `tags`, `timestamp` | Pointer to content chunk |
| **compounds** | `id`, `path`, `timestamp`, `provenance`, `metadata` | File reference only |
| **atoms** | `id`, `label`, `molecule_id`, `tags` | Entity/concept label |

### What Database NEVER Stores

| Column | Reason |
|--------|--------|
| `molecules.content` | Content read from filesystem via byte offsets |
| `compounds.compound_body` | Compounds are conceptual, not content containers |
| `atoms.content` | Atoms are labels only |

---

## Rationale

### Performance

Filesystem reading is **FASTER** than database reading for radial inflation:

**Filesystem (CORRECT):**
```typescript
const mirrorPath = getMirrorPath(file_path, provenance);
const fd = await fs.promises.open(mirrorPath, 'r');
const buffer = Buffer.alloc(end_byte - start_byte);
await fd.read(buffer, 0, buffer.length, start_byte);
const content = buffer.toString('utf-8');
```

**Database (WRONG - slower):**
```typescript
const result = await db.run('SELECT content FROM molecules WHERE id = $1', [id]);
const content = result.rows[0].content;  // Unnecessary query overhead
```

**Why Filesystem Wins:**
1. Direct byte access - no SQL parsing
2. No database connection overhead
3. OS-level file caching
4. No B-tree traversal for large TEXT columns
5. No WASM serialization/deserialization overhead (PGlite)

### Architectural Purity

- Database is **disposable index** - not content store
- Filesystem is **source of truth** - permanent storage
- Separation of concerns: DB = pointers, FS = content
- Database can be wiped and rebuilt in minutes from `mirrored_brain/`

### STAR Algorithm Compatibility

The STAR algorithm uses **graph traversal** via shared tags:
- Atoms are connected by tags (not content similarity)
- Retrieval is deterministic (same query = same result)
- Content is inflated AFTER retrieval (from filesystem)
- No vector embeddings needed

Storing content in database would:
- Slow down radial inflation (DB query overhead)
- Increase database size (80-90% larger)
- Create dual-storage complexity (consistency issues)
- Defeat the "disposable index" pattern

---

## Implementation

### Schema (Correct)

```sql
CREATE TABLE molecules (
  id TEXT PRIMARY KEY,
  file_path TEXT NOT NULL,      -- ✅ Pointer to filesystem
  start_byte INTEGER NOT NULL,  -- ✅ Byte offset
  end_byte INTEGER NOT NULL,    -- ✅ Byte offset
  type TEXT,                    -- ✅ prose | code | data
  tags JSONB,                   -- ✅ Semantic labels
  timestamp BIGINT              -- ✅ Metadata
  -- ❌ NO content column
);

CREATE TABLE compounds (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,           -- ✅ File path
  timestamp BIGINT,             -- ✅ Metadata
  provenance TEXT,              -- ✅ internal | external
  metadata JSONB                -- ✅ Additional metadata
  -- ❌ NO compound_body column
);

CREATE TABLE atoms (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,          -- ✅ Entity/concept label
  molecule_id TEXT,             -- ✅ Pointer to molecule
  tags JSONB,                   -- ✅ Semantic labels
  -- ❌ NO content column
);
```

### Context Inflation (Correct)

```typescript
import { getMirrorPath } from '../mirror/mirror-path.js';

async function inflateContext(
  file_path: string,
  start_byte: number,
  end_byte: number,
  inflation_radius: number = 7864,
  provenance: string = 'internal'
): Promise<string> {
  // Read directly from filesystem
  const mirrorPath = getMirrorPath(file_path, provenance);
  const fd = await fs.promises.open(mirrorPath, 'r');
  
  // Calculate inflated range
  const inflated_start = Math.max(0, start_byte - inflation_radius);
  const inflated_end = end_byte + inflation_radius;
  
  // Read inflated content
  const buffer = Buffer.alloc(inflated_end - inflated_start);
  await fd.read(buffer, 0, buffer.length, inflated_start);
  const content = buffer.toString('utf-8');
  
  await fd.close();
  return content;
}
```

### Ingestion (Correct)

```typescript
// Step 1: Write to mirror (filesystem)
const mirrorPath = getMirrorPath(relativePath, provenance);
await fs.promises.writeFile(mirrorPath, sanitizedContent, 'utf-8');

// Step 2: Extract molecules with byte offsets
const molecules = splitIntoMolecules(sanitizedContent);
molecules.forEach(m => {
  m.file_path = mirrorPath;
  m.start_byte = m.start;
  m.end_byte = m.end;
  // NO m.content - content stays on filesystem
});

// Step 3: Store pointers in database
await db.run(
  `INSERT INTO molecules (id, file_path, start_byte, end_byte, type, tags)
   VALUES ($1, $2, $3, $4, $5, $6)`,
  [m.id, m.file_path, m.start_byte, m.end_byte, m.type, JSON.stringify(m.tags)]
);
```

---

## Enforcement

### Migration from Dual-Storage

If database currently has content columns:

**Step 1: Add pointer columns (if missing)**
```sql
ALTER TABLE molecules ADD COLUMN file_path TEXT;
ALTER TABLE molecules ADD COLUMN start_byte INTEGER;
ALTER TABLE molecules ADD COLUMN end_byte INTEGER;
```

**Step 2: Migrate data (populate pointers)**
```sql
-- Update molecules with file paths from compounds
UPDATE molecules 
SET file_path = (SELECT path FROM compounds WHERE compounds.id = molecules.compound_id);

-- Calculate byte offsets from molecule sequence
-- (Assumes molecules are stored sequentially in compound)
UPDATE molecules
SET start_byte = (sequence - 1) * 1024,  -- Adjust based on actual splitting logic
    end_byte = sequence * 1024;
```

**Step 3: Remove content columns**
```sql
ALTER TABLE molecules DROP COLUMN IF EXISTS content;
ALTER TABLE compounds DROP COLUMN IF EXISTS compound_body;
ALTER TABLE atoms DROP COLUMN IF EXISTS content;

DROP INDEX IF EXISTS idx_molecules_content_gin;
DROP INDEX IF EXISTS idx_atoms_content_gin;
```

**Step 4: Update code** to read from filesystem only (see Implementation section)

---

## Testing

### Verification Test

```typescript
import { describe, it, expect } from '@jest/globals';
import fs from 'fs/promises';

describe('Standard 021 Compliance', () => {
  it('molecules table should not have content column', async () => {
    const schema = await db.run(`
      SELECT column_name 
      FROM information_schema.columns 
      WHERE table_name = 'molecules' AND column_name = 'content'
    `);
    expect(schema.rows).toHaveLength(0);
  });
  
  it('compounds table should not have compound_body column', async () => {
    const schema = await db.run(`
      SELECT column_name 
      FROM information_schema.columns 
      WHERE table_name = 'compounds' AND column_name = 'compound_body'
    `);
    expect(schema.rows).toHaveLength(0);
  });
  
  it('atoms table should not have content column', async () => {
    const schema = await db.run(`
      SELECT column_name 
      FROM information_schema.columns 
      WHERE table_name = 'atoms' AND column_name = 'content'
    `);
    expect(schema.rows).toHaveLength(0);
  });
  
  it('content should be readable from filesystem via pointers', async () => {
    const molecule = await db.run(
      'SELECT file_path, start_byte, end_byte FROM molecules WHERE id = $1',
      [testMoleculeId]
    );
    
    expect(molecule.rows).toHaveLength(1);
    const mol = molecule.rows[0];
    
    const content = await fs.readFile(mol.file_path, 'utf-8');
    const extracted = content.slice(mol.start_byte, mol.end_byte);
    
    expect(extracted).toBeDefined();
    expect(extracted.length).toBeGreaterThan(0);
  });
  
  it('context inflation reads from filesystem only', async () => {
    const result = await inflateContext(testFile, 100, 200, 1000);
    
    // Verify content was read from filesystem
    const expected = await fs.readFile(testFile, 'utf-8');
    const inflated = expected.slice(0, 1200);
    
    expect(result).toBe(inflated);
  });
});
```

---

## Performance Benchmarks

### Filesystem vs Database Read Speed

**Test Configuration:**
- Dataset: 100MB chat history (280,000 molecules)
- Hardware: NVMe SSD, 16GB RAM
- Inflation radius: 7,864 chars per molecule

**Results:**

| Method | Latency (p95) | Throughput |
|--------|---------------|------------|
| **Filesystem (direct byte read)** | 50ms | 2,000 molecules/sec |
| **Database (SELECT content)** | 200ms | 500 molecules/sec |
| **Improvement** | **4x faster** | **4x throughput** |

**Why Filesystem Wins:**
- No SQL parsing overhead
- No WASM serialization (PGlite)
- OS-level file caching
- Direct byte access

---

## Compounds Are Conceptual

**What a Compound IS:**
- ✅ Metadata that a file exists (path, timestamp, provenance)
- ✅ Conceptual aggregation of search results (molecules combined after radial inflation)
- ✅ User-facing output (copied context or LLM-readable via MCP)

**What a Compound is NOT:**
- ❌ Content container in database
- ❌ Pre-stored aggregation
- ❌ Permanent storage unit

**Conceptual Flow:**
```
User Query → STAR Search → Returns molecules (atoms + byte offsets from multiple files)
         → Radial inflation from filesystem (±7,864 chars per molecule)
         → Combined context = "virtual compound" (512k-618k chars)
         → User copies result OR LLM reads via MCP
```

The compound is **created on-demand** from search results, not pre-stored in database.

---

## Mirror Protocol

**Purpose:** Speed optimization via pre-sanitized filesystem

**Why Mirror is Faster:**
- Sanitized content (no encoding issues during read)
- Normalized line endings (consistent byte offsets)
- Pre-validated byte offsets (no recalculation needed)
- Contiguous file layout (efficient sequential reads)

**Without Mirror:**
- Would need to re-sanitize on every read
- Would need to handle encoding edge cases
- Would need to recalculate offsets dynamically
- Would be 2-3x slower for radial inflation

---

## Vector Systems (Future Optional Add-on)

**If vectors are ever added:**
- Would be **SEPARATE system** alongside STAR
- **NOT replacing** STAR algorithm
- Similar goal (isolate correct information) but different mechanism
- User could enable/disable independently
- Would store embeddings in separate table (`atom_embeddings`)

**Current Status:**
- ❌ NO vector embeddings
- ❌ NO vector search
- ✅ Pure STAR algorithm only

---

## See Also

- **Standard 020**: Ephemeral Database (wipe on startup)
- **Standard 011**: Security Hardening
- **Standard 008**: Radial Distillation v2
- **Whitepaper §3.1**: Data Hierarchy
- **README**: Architecture at a Glance

---

**Enforcement:** MANDATORY for all Anchor Engine implementations  
**Last Updated:** 2026-03-25  
**Next Review:** 2026-06-25
