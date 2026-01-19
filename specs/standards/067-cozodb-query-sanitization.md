# Standard 066: CozoDB Query Sanitization

**Category:** Database / Reliability
**Status:** Approved
**Date:** 2026-01-19

## The Triangle of Pain

### 1. What Happened?
The CozoDB FTS (Full-Text Search) parser is highly sensitive to special characters. Queries containing periods (e.g., `arXiv.org`), hyphens, or brackets would trigger opaque `query parser unexpected input` errors, crashing the search service and returning zero results.

### 2. The Cost
- 2 hours of debugging silent search failures.
- Application instability when users entered technical terms.
- Difficulty in retrieving memories related to specific file extensions or domain names.

### 3. The Rule
**All user-provided search terms MUST be passed through the `sanitizeFtsQuery` helper before being embedded into a Datalog query.**

#### The Implementation
```typescript
function sanitizeFtsQuery(query: string): string {
  return query
    .replace(/[^a-zA-Z0-9\s]/g, ' ') // Replace all non-alphanumeric chars with spaces
    .replace(/\s+/g, ' ')            // Collapse multiple spaces
    .trim()
    .toLowerCase();
}
```

#### Guidelines
- **FTS-Only**: This sanitization applies specifically to terms destined for `~memory:content_fts`.
- **Preserve Projection**: Sanitization should ONLY affect the value of the `$query` parameter, not the projection variables (e.g., `?[id, content...]`).
- **Reserved Keywords**: Be cautious of reserved words in Datalog; ensuring the query is a string literal passed as a parameter (using `$`) is the safest approach.
