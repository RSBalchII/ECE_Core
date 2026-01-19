# Standard 066: Human-Readable Mirror Protocol (Re-Hydration)

## 1. The Core Philosophy
**"Atomize for the Graph, Bundle for the Human."**

The Database (`CozoDB`) requires granularity (Atoms) for effective retrieval.
The User (`The Architect`) requires coherence (Documents) for effective reading and editing.
The Mirror must bridge this gap by **Re-Hydrating** atoms into document-like structures.

## 2. The Problem of Fragmentation
Raw mirroring of atoms (1:1 mapping) results in:
- **Inode Exhaustion:** 100k+ small files degrade filesystem performance.
- **Cognitive Load:** Users cannot "read" a directory of UUIDs.
- **Editor Crash:** IDEs like VS Code consume GBs of RAM indexing the file tree.

## 3. The Re-Hydration Protocol
When syncing the `mirrored_brain/` directory, the Engine MUST:

### A. Group by Source
Instead of iterating atoms, iterate **Sources**.
```sql
?[source_path, atom_content, sequence] := *atoms{source_path, content, sequence}
:order source_path, sequence
```

### B. Concatenation Strategy
Atoms belonging to the same `source_path` are written to a single file.
**Format:**
```markdown
# Source: relative/path/to/original.md

[Content of Atom 1]

---
[Content of Atom 2]
```

### C. The "Orphan" Handling
If an atom lacks a clear `source_path` (e.g., generated insights, chat logs), it should be bundled by **Time** (Daily/Weekly Logs) or **Topic** (Tag Buckets) to prevent directory pollution.

## 4. Performance Target
- **Max Files in Root:** < 50
- **Max Files per Subdir:** < 100
- **Sync Speed:** < 2s for 10k atoms (via bulk write).
