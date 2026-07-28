# Standard 003: MCP Tool Interface

**Status:** Active  
**Date:** 2026-03-13  
**Supersedes:** Inline comments in `mcp-server/index.ts`

## Context
Anchor Engine exposes its core capabilities via an MCP server, allowing any MCP‑compatible client (Claude, Cursor, Qwen Code, etc.) to query and interact with the memory graph. To ensure consistent behavior across clients, the tool schemas must be formally defined.

## Requirements
The MCP server must expose the following tools with the specified input/output schemas:

### `anchor_query`
- **Purpose:** Semantic search over the memory graph.
- **Input:** `{ query: string, max_results?: number, buckets?: string[] }`
- **Output:** Array of results with `content`, `score`, `source`, `tags`, and `provenance`.

### `anchor_distill`
- **Purpose:** Run radial distillation on a corpus or seed.
- **Input:** `{ seed?: string, radius?: number, output_format?: 'yaml'|'md' }`
- **Output:** `{ output_path: string, stats: { lines_total, lines_unique, compression_ratio, duration_ms } }`

### `anchor_illuminate`
- **Purpose:** BFS graph traversal from a seed.
- **Input:** `{ seed: string, depth?: number }`
- **Output:** List of connected nodes with edges and scores.

### `anchor_read_file`
- **Purpose:** Read a file with optional line ranges (token‑efficient).
- **Input:** `{ path: string, start_line?: number, end_line?: number }`
- **Output:** File content (or slice).

### `anchor_list_compounds`
- **Purpose:** List available compounds (source files).
- **Input:** `{ filter?: string }`
- **Output:** Array of compound IDs with metadata.

## Implementation Notes
- All tools must validate inputs using Zod.
- Errors must be returned with clear messages and appropriate HTTP status codes (when applicable).