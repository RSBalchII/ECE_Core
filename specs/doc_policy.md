# Documentation Policy (Context-Engine)

**Master Policy for all directories. Code is authoritative; documentation supports it.**

---

## Rule 1: Minimize Documentation

- Code is the source of truth. Documentation explains *why* and guides *how*, but never replaces code.
- Default assumption: No docs needed unless setup is genuinely ambiguous or painful.
- LLM-generated reference docs are archived to `/archive/` after they're used.

---

## Rule 2: Allowed Documentation Per Directory

### Root Level
- **README.md** — 100 words. Answer: "What is this repo?"
- **CHANGELOG.md** — Version history and major changes
- **STARTUP.md** — Quick start (if needed)
- **specs/** — Central spec layer (see Rule 3)

### `backend/`, `tools/`, `extension/`, `scripts/`
- **README.md** — Single sentence. Answer: "What does this directory do?"
- **CONFIGURATION.md** — Only if env setup is non-obvious (backend only)
- **No additional .md files** in directory root (see Rule 3)

### `backend/src/`, `tools/src/`, `extension/src/`
- No separate documentation. Inline code comments with `#file:specs/...` references.

---

## Rule 3: Specification Layer (`specs/`)

The `specs/` directory is the **single source of architectural truth**.

### Core Files
- **spec.md** — High-level system architecture (read this first)
- **plan.md** — Roadmap and phases
- **tasks.md** — Implementation task queue
- **doc_policy.md** — This file (documentation governance)
- **mlc-urls.md** — Registry of verified MLC-LLM model URLs (see Rule 3.1)

### Architecture Subdirectory
- **specs/architecture/** — Deep technical specifications
  - **sovereign-wasm.spec.md** — Browser-native layer (WebGPU, CozoDB, model-server-chat, builder)
  - **memory-layer.spec.md** — Neo4j/Redis architecture and schemas
  - **extension-bridge.spec.md** — Chrome extension design (injection, pause triggers)
  - **agents.spec.md** — Agent system (Verifier, Distiller, Archivist)
  - **api.spec.md** — FastAPI endpoints and protocols

### Where Each Spec Goes
- **Architectural overview or design decisions?** → `specs/spec.md`
- **Multi-phase roadmap?** → `specs/plan.md`
- **Implementation tasks?** → `specs/tasks.md`
- **Deep technical details** (schemas, data flow, algorithms)? → `specs/architecture/<domain>.spec.md`
- **Local directory context** (e.g., "what does scripts/ do")? → `README.md` in that directory

---

## Rule 4: Deprecated/Generated Documentation

All LLM-generated reference documentation (tutorials, examples, detailed walkthroughs) should be:
1. **Used locally** (for context during development)
2. **Archived to `/archive/`** after they served their purpose
3. **Never** left in active project root or major directories

Examples of archived docs:
- `archive/docs_removed/` — Outdated technical docs
- `archive/anchor/` — Deprecated CLI interface docs
- `archive/setup_docs/` — Legacy setup guides

---

## Rule 5: Cross-Referencing Specs

Within any spec file, use markdown links to other specs:

```markdown
For memory architecture, see [Memory Layer Spec](architecture/memory-layer.spec.md).
For browser integration, see [Sovereign WASM Spec](architecture/sovereign-wasm.spec.md).
```

In code files, use comments to reference specs:
```python
# Graph-R1 reasoning flow (see specs/architecture/agents.spec.md)
def graph_r1_query():
    pass
```

---

## Rule 6: Truth Precedence

If **code conflicts with documentation**:
1. Code is correct
2. Update the relevant spec file immediately
3. Add a git note explaining the discrepancy

If **multiple specs conflict**:
1. `spec.md` is authoritative for architecture
2. `architecture/*.spec.md` fills in implementation details
3. Code is the final arbiter

---

## Rule 7: Reality Constraint

Documentation must never:
- Contradict the "Empirical Distrust" protocol (retrieve > internal knowledge)
- Promise features not implemented in code
- Reference deprecated repositories or APIs without clear deprecation notices

---

## Enforcement

- **Review checklist:** Before merging PRs, verify no new .md files are scattered (should only be in specs/ or as single README.md per directory)
- **Quarterly cleanup:** Archive generated/reference docs older than 3 months
- **Broken links:** Use `specs/architecture/` links; verify they exist before committing

---

## Quick Reference

| Question | Answer |
|----------|--------|
| Where's the architecture? | `specs/spec.md` |
| Where's the roadmap? | `specs/plan.md` |
| Where are the tasks? | `specs/tasks.md` |
| How do I set up the backend? | `backend/CONFIGURATION.md` |
| What's in tools/? | `tools/README.md` |
| How do I understand WASM layer? | `specs/architecture/sovereign-wasm.spec.md` |
| How do Neo4j/Redis work? | `specs/architecture/memory-layer.spec.md` |
| How does the extension work? | `specs/architecture/extension-bridge.spec.md` |
| Where are old docs? | `archive/docs_removed/` |

---

## CozoDB Import Format & Recovery

**Purpose:** Describe the canonical JSON format used for bulk imports into the browser CozoDB instance and recovery steps when a Schema Detachment occurs.

**Note:** As of HTML pivot, CozoDB runs entirely in browser WASM with IndexedDB persistence. Recovery procedures apply to browser-native tools in `tools/` directory.

### Canonical Import JSON
CozoDB expects a top-level JSON object with a `relations` array. Each relation should look like this:

```json
{
  "relations": [
    {
      "name": "memory",
      "headers": ["id","timestamp","role","content","source","embedding"],
      "rows": [
        ["id-1", 1688790000000, "system", "file text...", "path/to/file.md", null],
        [...]
      ]
    }
  ]
}
```

- `id`: string, unique identifier (UUID or deterministic hash)
- `timestamp`: integer, Unix ms
- `role`: string, e.g., `system` or `user`
- `content`: string, textual content (truncate if exceedingly large)
- `source`: string, origin path or descriptor
- `embedding`: either an array of floats (embedding vector) or `null` if embeddings will be computed later

### Recovery: Schema Detachment
When `export_relations({})` returns `{"message":"missing field `relations` ..."}` or queries report `query::relation_not_found`:
1. Attempt non-destructive reattach:
```js
await window.db.run(":create memory { id: String => timestamp: Int, role: String, content: String, source: String, embedding: <F32; 384> } IF NOT EXISTS");
```
2. If reattach fails, export raw OPFS/IndexedDB blobs and decode them locally using `tools/decode_cozo_blob.py`.
3. Prefer bulk import from canonical source (`cozo_import_memory.json`) rather than reimporting individual rows.

### Tooling & Best Practices
- Use `tools/prepare_cozo_import.py` to create `cozo_import_memory.json` from `combined_memory.json`.
- For a guaranteed atomic result: nuke the DB and `Force Import Relations from JSON` (or use `db.import_relations(payload)` in Console) with the produced file.
- After import, run `export_relations({})` and persist the result (backup) plus verify by running `?[count] := *memory{id}`.

---

**Last Updated:** 2025-12-15  
**Version:** 1.0  
**Policy Owner:** Architecture Council
