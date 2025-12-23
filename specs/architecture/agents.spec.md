# Agent Architecture (Sovereign Edition)

**Status:** Planned / Partially Implemented in JS

The Sovereign Edition moves agentic logic from Python to JavaScript (Root Coda).

## Core Agents

### 1. The Archivist (Memory Writer)
- **Role:** Persists chat interactions to CozoDB.
- **Implementation:** `saveTurn()` in `model-server-chat.html`.
- **Status:** Active. Writes `*memory` relations with `msg_` IDs.

### 2. The Distiller (Dreamer)
- **Role:** Background consolidation and vectorization.
- **Implementation:** `tools/root-dreamer.html`.
- **Logic:**
  - Scans for orphan memories (no embedding).
  - Generates synthetic thoughts/connections.
  - Updates the Graph.

### 3. The Verifier (Critic)
- **Role:** Fact-checking and loop termination.
- **Implementation:** Integrated into "Graph-R1" Reasoning Loop (`ContextManager`).
- **Status:** Implicit in the `executeR1Loop` via "Self-Correction" prompt prompts.

## Future Plans
- Formalize `Verifier` as a separate Web Worker for parallel fact-checking.
