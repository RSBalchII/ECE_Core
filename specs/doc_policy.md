# Documentation Policy (Root Coda)

**Status:** Active | **Authority:** Human-Locked

## Core Philosophy
1. **Code is King:** Code is the only source of truth. Documentation is a map, not the territory.
2. **Visuals over Text:** Prefer Mermaid diagrams to paragraphs.
3. **Brevity:** Text sections must be <500 characters.

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

### 4. Local Context (`*/README.md`)
*   **Role:** Directory-specific context.
*   **Limit:** 1 sentence explaining the folder's purpose.

## LLM Protocol
1. **Read-First:** Always read `specs/spec.md` before answering architectural questions.
2. **Drafting:** When asked to document, produce **Mermaid diagrams** and short summaries.
3. **Editing:** Do not modify `specs/doc_policy.md` or `specs/spec.md` structure unless explicitly instructed.
4. **Archival:** Move stale docs to `archive/` immediately.

---
*Verified by Architecture Council. Edited by Humans Only.*
