<!-- ARCHIVED: This document was moved as part of documentation consolidation. See specs/doc_policy.md for active doc list. -->

<!-- Original content preserved for historical reference -->

````markdown
<!-- ARCHIVED: Full ecosystem startup guide moved to archive/docs_removed/ecosystem.md -->
```
┌─────────────────────────────────────────────────────────┐
│                   Your ECE Stack                        │
│                                                         │
│  1. llama-server (Inference Engine)                    │
│     Port 8080 - GPU-accelerated LLM                    │
│                                                         │
│  2. ECE_Core (Memory & Reasoning)                      │
│     Port 8000 - Coda, Memory, UTCP Services            │
│     Port 6379 - Redis cache                            │
│     Port 8006 - UTCP Filesystem                        │
│                                                         │
│  3. Anchor (Terminal Interface)                        │
│     TUI - Your command center                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start (Full System)

### Terminal 1: LLM Inference Engine
```bash
cd C:\Users\rsbiiw\Projects
start-llama-server.bat
```
# ... (content preserved) - trimmed for archival reference

---

## Neo4j Graph Database (2025-11-12)

### Status: ✅ Embedded and Working

<!-- End archived content -->
````
