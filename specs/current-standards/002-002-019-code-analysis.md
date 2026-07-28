# Standard 019: Code Analysis Integration

**Status:** Active  
**Version:** 1.0.0  
**Created:** 2026-03-22  
**Author:** Anchor Engine Team

---

## Overview

This standard defines how Anchor Engine integrates code analysis tools into the GitHub repository ingestion pipeline. When enabled, the system runs a predefined toolchain of static analysis tools and ingests their reports as searchable knowledge.

---

## 1. Design Principles

### 1.1 Simplicity First
- **One toggle, zero configuration** - Users enable analysis with a single checkbox
- **Default toolchain** - No need to select which tools to run
- **Graceful degradation** - If a tool fails, skip it and continue

### 1.2 Local-First
- All analysis runs on the user's machine
- No external services or cloud processing
- Results are stored in the local knowledge graph

### 1.3 Semantic Integration
- Analysis results are ingested as atoms/molecules
- Tagged with `#analysis` for easy filtering
- Linked to source files via file path tags

---

## 2. Toolchain

### 2.1 Supported Tools

| Tool | Purpose | Languages | Output Format |
|------|---------|-----------|---------------|
| ESLint | Code style & errors | JS/TS | JSON |
| ts-prune | Unused exports | TypeScript | Text/JSON |
| dependency-cruiser | Module dependencies | JS/TS | JSON |
| jscpd | Duplicate code | Multi-language | JSON |

### 2.2 Tool Selection

Tools are automatically selected based on detected languages:

1. **Language Detection**: Scan file extensions in the repository
2. **Tool Matching**: Run tools that support detected languages
3. **Skip Inapplicable**: Silently skip tools that don't apply

### 2.3 Default Configurations

If a repository lacks tool configuration files, Anchor Engine provides minimal defaults:

```json
// .eslintrc.json (generated if missing)
{
  "root": true,
  "parser": "@typescript-eslint/parser",
  "parserOptions": {
    "ecmaVersion": 2022,
    "sourceType": "module"
  },
  "rules": {
    "no-unused-vars": "warn",
    "no-undef": "error"
  },
  "env": {
    "node": true,
    "es2022": true
  }
}
```

```json
// tsconfig.json (generated if missing)
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "node",
    "esModuleInterop": true,
    "strict": false,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules", "dist", ".anchor-analysis"]
}
```

---

## 3. Execution Model

### 3.1 Timing

Analysis runs **after** source file ingestion, before cleanup:

```
1. Download tarball
2. Extract to temp directory
3. Walk and ingest source files
4. Run code analysis (if enabled)  ← HERE
5. Ingest analysis results
6. Cleanup temp directory
```

### 3.2 Timeout Protection

Each tool has a **60-second timeout**:

- If a tool times out, log a warning and skip
- Other tools continue running
- Overall ingestion is not blocked

### 3.3 Sequential Execution

Tools run **sequentially** (not parallel) to:

- Avoid resource contention
- Provide predictable memory usage
- Simplify error handling

---

## 4. Output Format

### 4.1 Normalized Analysis Result

All tool outputs are normalized to a consistent format:

```typescript
interface AnalysisResult {
  tool: string;        // 'eslint' | 'ts-prune' | 'dependency-cruiser' | 'jscpd'
  file: string;        // Relative path from repo root
  line?: number;       // Line number (if applicable)
  column?: number;     // Column number (if applicable)
  severity: 'error' | 'warning' | 'info';
  message: string;     // Human-readable description
  rule?: string;       // Rule ID (e.g., 'no-unused-vars')
  metadata?: object;   // Tool-specific data
}
```

### 4.2 Storage

Analysis results are stored in two formats:

1. **JSONL** (ingested): `analysis.jsonl` - One result per line
2. **Raw JSON** (debug): `analysis-raw.json` - Full tool output

### 4.3 Tags

All analysis molecules receive the `#analysis` tag, plus tool-specific tags:

- `#eslint` for ESLint findings
- `#ts-prune` for unused exports
- `#dependency-cruiser` for dependency issues
- `#jscpd` for duplicate code

---

## 5. API Integration

### 5.1 GitHub Ingestion Endpoint

```http
POST /v1/github/repos
Content-Type: application/json

{
  "url": "https://github.com/user/repo",
  "branch": "main",
  "bucket": "code",
  "include_history": true,
  "run_analysis": true    // NEW: Enable code analysis
}
```

### 5.2 Response

```json
{
  "id": "github_user_repo_main",
  "status": "ingesting",
  "include_history": true,
  "run_analysis": true,
  "message": "Started ingestion for user/repo (with commit history and code analysis)"
}
```

### 5.3 Manual Sync

```http
POST /v1/github/repos/:id/sync
Content-Type: application/json

{
  "run_analysis": true
}
```

---

## 6. UI Integration

### 6.1 GitHub Modal

A new checkbox is added to the GitHub ingestion modal:

```
[ ] Include full commit history (search code changes over time)
[ ] Run code analysis (ESLint, unused exports, duplicates)
```

### 6.2 Default State

- **Include commit history**: Checked by default
- **Run code analysis**: Unchecked by default

---

## 7. Re-ingestion Behavior

### 7.1 Quarantine Old Results

When a repository is re-synced with analysis enabled:

1. **Quarantine** old analysis atoms (add `#quarantined` tag)
2. **Run fresh analysis** on updated code
3. **Ingest new results** with current timestamps

### 7.2 Consistency

This matches the behavior for source code atoms (Standard 115, Section 4.5).

---

## 8. Error Handling

### 8.1 Tool Failures

| Failure Type | Behavior |
|--------------|----------|
| Tool not installed | Skip with warning |
| Tool times out | Skip with warning |
| Tool returns error | Log error, skip tool |
| Parse error | Log error, skip tool |

### 8.2 Overall Ingestion

Analysis failures **do not** fail the overall ingestion:

- Source files are still ingested
- Other tools still run
- Error is logged for debugging

---

## 9. Performance Considerations

### 9.1 Large Repositories

For repositories with many files:

- Each tool has a 60-second timeout
- Tools run sequentially to avoid memory spikes
- Analysis can be disabled for faster ingestion

### 9.2 Resource Usage

| Tool | Typical Memory | Typical Time |
|------|---------------|--------------|
| ESLint | 100-500 MB | 5-30s |
| ts-prune | 50-200 MB | 2-15s |
| dependency-cruiser | 50-200 MB | 2-15s |
| jscpd | 100-300 MB | 5-20s |

---

## 10. Extensibility

### 10.1 Adding New Tools

To add a new analysis tool:

1. Add tool configuration to `TOOL_CONFIGS` array
2. Implement a parser function
3. Add to `package.json` dependencies

```typescript
// In code-analyzer.ts
const TOOL_CONFIGS: ToolConfig[] = [
  // ... existing tools
  {
    name: 'new-tool',
    command: 'npx',
    args: ['new-tool', '--json'],
    fileExtensions: ['.py'],
    requiresConfig: [],
    parser: parseNewToolOutput
  }
];
```

### 10.2 Language Support

To add support for a new language:

1. Add file extension to `LANGUAGE_MAP`
2. Add language to `detectLanguages()` method
3. Update tool `fileExtensions` arrays

---

## 11. Dependencies

### 11.1 Required Packages

```json
{
  "devDependencies": {
    "dependency-cruiser": "^16.0.0",
    "eslint": "^8.53.0",
    "jscpd": "^4.0.5",
    "ts-prune": "^0.10.3"
  }
}
```

### 11.2 Installation

```bash
npm install --save-dev dependency-cruiser jscpd ts-prune
```

Note: ESLint is already a project dependency.

---

## 12. Testing

### 12.1 Manual Testing

```bash
# Start the engine
npm run start

# Ingest a repo with analysis
curl -X POST http://localhost:3160/v1/github/repos \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://github.com/user/repo",
    "run_analysis": true
  }'

# Search for analysis results
curl -X POST http://localhost:3160/v1/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "eslint error", "buckets": ["analysis"]}'
```

### 12.2 Verification

1. Check logs for analysis tool execution
2. Verify analysis.jsonl file creation
3. Search for `#analysis` tagged content
4. Verify file path linking works

---

## 13. Future Enhancements

### 13.1 Planned Features

- **Python support**: Add pylint, mypy, bandit
- **Rust support**: Add clippy, rust-analyzer
- **Go support**: Add go vet, staticcheck
- **Custom toolchain**: Allow users to configure which tools run
- **Severity filtering**: Only ingest errors/warnings above a threshold

### 13.2 Status Endpoint

Future versions may add a `/v1/github/repos/:id/analysis` endpoint to:

- Check analysis status
- View summary statistics
- Download raw reports

---

## References

- **Standard 115**: GitHub Repository Ingestion
- **Standard 012**: Quarantine Protocol
- **Standard 009**: Illuminate & Explore

---

**Last Updated:** 2026-03-22  
**Maintainer:** Anchor Engine Team