# Documentation Policy (Root Coda)

**Status:** Active | **Authority:** Human-Locked

## Core Philosophy
1. **Code is King:** Code is the only source of truth. Documentation is a map, not the territory.
2. **Visuals over Text:** Prefer Mermaid diagrams to paragraphs.
3. **Brevity:** Text sections must be <500 characters.
4. **Pain into Patterns:** Every major bug must become a Standard.

## Structure

### 1. The Blueprint (`specs/spec.md`)
*   **Role:** The single architectural source of truth.
*   **Format:** "Visual Monolith".
*   **Content:** High-level diagrams (Kernel, Memory, Logic, Bridge). No deep implementation details.

### 2. The Tracker (`specs/tasks.md`)
*   **Role:** Current work queue.
*   **Format:** Checklist.
*   **Maintenance:** Updated by Agents after every major task.

### 3. The Roadmap (`specs/plan.md`)
*   **Role:** Strategic vision.
*   **Format:** Phased goals.

### 4. Standards (`specs/standards/*.md`)
*   **Role:** Institutional Memory (The "Laws" of the codebase).
*   **Trigger:** Created after any bug that took >1 hour to fix.
*   **Format:** "The Triangle of Pain"
    1.  **What Happened:** The specific failure mode (e.g., "Bridge crashed on start").
    2.  **The Cost:** The impact (e.g., "3 hours debugging Unicode errors").
    3.  **The Rule:** The permanent constraint (e.g., "Force UTF-8 encoding on Windows stdout").

### 5. Local Context (`*/README.md`)
*   **Role:** Directory-specific context.
*   **Limit:** 1 sentence explaining the folder's purpose.

## LLM Protocol
1. **Read-First:** Always read `specs/spec.md` AND `specs/standards/` before coding.
2. **Drafting:** When asked to document, produce **Mermaid diagrams** and short summaries.
3. **Editing:** Do not modify `specs/doc_policy.md` or `specs/spec.md` structure unless explicitly instructed.
4. **Archival:** Move stale docs to `archive/` immediately.
5. **Enforcement:** If a solution violates a Standard, reject it immediately.

---
*Verified by Architecture Council. Edited by Humans Only.*
