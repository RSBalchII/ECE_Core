<!-- ARCHIVED: Architecture doc moved to archive/docs_removed/docs/architecture.md -->

````markdown
# ECE_Core Architecture Overview

<!-- Preserved original doc summary for historical reference. See original location for live specs in `specs/spec.md` -->

Components:
- `core/config.py` (`Settings`): centralized configuration for LLM, memory, retrieval, server, security, MCP.
- `memory.py` (`TieredMemory`): Redis active context + Neo4j summaries; token counting; init/close lifecycle.
<!-- trimmed -->
````
