# Anchor Engine Standards Index

This directory contains **33 active architecture standards** for Anchor Engine, organized by category.

---

## 📊 Standards Overview

| Category | Standards | Purpose |
|----------|-----------|---------|
| **Database & Memory** | 5 | Data architecture, ephemeral database, pointer-only storage |
| **Security** | 4 | Security hardening, auth bypass, path traversal, API key validation |
| **Configuration & Paths** | 3 | Configuration management, path validation, path usage |
| **Search & Retrieval** | 5 | MCP tools, streaming search, mobile optimization, illumination, algorithm reference |
| **Distillation** | 6 | Radial distillation, zero-copy deduplication, output storage, self-contamination prevention, tag-based mode |
| **Operations & Logging** | 2 | Operational visibility, pain point logging |
| **Performance** | 1 | Adaptive concurrency control |
| **Robustness** | 1 | WASM fallback |
| **Data Integrity** | 1 | Data integrity operations |
| **Testing** | 2 | MCP integration testing, unified test pipeline |
| **Dependencies** | 1 | Dependency validation |
| **Analysis** | 1 | Code analysis |
| **Documentation** | 1 | Documentation hygiene |

---

## 🔑 Quick Access

### Foundation Standards

| # | Standard | File |
|---|----------|------|
| **001** | Memory-Safe Ingestion | [database-memory/001-memory-safe-ingestion.md](database-memory/001-memory-safe-ingestion.md) |
| **002** | Reproducible Benchmarking | [database-memory/002-reproducible-benchmarking.md](database-memory/002-reproducible-benchmarking.md) |

### Database & Memory

| # | Standard | File |
|---|----------|------|
| **007** | PGlite Memory Optimization | [database-memory/007-pglite-memory-optimization.md](database-memory/007-pglite-memory-optimization.md) |
| **020** | Ephemeral Database | [database-memory/020-ephemeral-database.md](database-memory/020-ephemeral-database.md) |
| **021** | Pointer-Only Storage | [database-memory/021-pointer-only-storage.md](database-memory/021-pointer-only-storage.md) |

### Security Standards (P0 Critical)

| # | Standard | File | Priority |
|---|----------|------|----------|
| **023** | Authentication Bypass Prevention | [security/023-auth-bypass-prevention.md](security/023-auth-bypass-prevention.md) | P0 |
| **025** | Path Traversal Prevention | [security/025-path-traversal-prevention.md](security/025-path-traversal-prevention.md) | P0 |
| **024** | API Key Strength Validation | [security/024-api-key-strength-validation.md](security/024-api-key-strength-validation.md) | P0 |
| **011** | Security Hardening | [security/011-security-hardening.md](security/011-security-hardening.md) | P0 |

### Configuration & Paths

| # | Standard | File |
|---|----------|------|
| **015** | Configuration Management | [configuration-paths/015-configuration-management.md](configuration-paths/015-configuration-management.md) |
| **018** | Configuration Validation | [configuration-paths/018-configuration-validation.md](configuration-paths/018-configuration-validation.md) |
| **029** | Path Usage Validation | [configuration-paths/029-path-usage-validation.md](configuration-paths/029-path-usage-validation.md) |

### Search & Retrieval

| # | Standard | File |
|---|----------|------|
| **003** | MCP Tool Interface | [search-retrieval/003-mcp-tool-interface.md](search-retrieval/003-mcp-tool-interface.md) |
| **004** | Streaming Search | [search-retrieval/004-streaming-search.md](search-retrieval/004-streaming-search.md) |
| **006** | Mobile Search Optimization | [search-retrieval/006-mobile-search-optimization.md](search-retrieval/006-mobile-search-optimization.md) |
| **009** | Illuminate BFS Traversal | [search-retrieval/009-illuminate-bfs-traversal.md](search-retrieval/009-illuminate-bfs-traversal.md) |
| **031** | Search Algorithms Comprehensive Reference | [search-retrieval/031-search-algorithms-comprehensive.md](search-retrieval/031-search-algorithms-comprehensive.md) |

### Distillation

| # | Standard | File |
|---|----------|------|
| **008** | Radial Distillation | [distillation/008-radial-distillation.md](distillation/008-radial-distillation.md) |
| **010** | Radial Distillation v2 | [distillation/010-radial-distillation-v2.md](distillation/010-radial-distillation-v2.md) |
| **026** | Zero-Copy Deduplication | [distillation/026-zero-copy-dedup.md](distillation/026-zero-copy-dedup.md) |
| **027** | Distillation Output Storage | [distillation/027-distillation-output-storage.md](distillation/027-distillation-output-storage.md) |
| **028** | Self-Contamination Prevention | [distillation/028-self-contamination-prevention.md](distillation/028-self-contamination-prevention.md) |
| **029** | Tag-Based Distillation Mode | [distillation/029-tag-based-distillation.md](distillation/029-tag-based-distillation.md) |

### Operations & Logging

| # | Standard | File |
|---|----------|------|
| **014** | Operational Visibility | [operations-logging/014-operational-visibility.md](operations-logging/014-operational-visibility.md) |
| **027** | Pain Point Logging | [operations-logging/027-pain-point-logging.md](operations-logging/027-pain-point-logging.md) |

### Performance & Robustness

| # | Standard | File |
|---|----------|------|
| **005** | Adaptive Concurrency Control | [performance/005-adaptive-concurrency-control.md](performance/005-adaptive-concurrency-control.md) |
| **013** | WASM Fallback | [robustness/013-wasm-fallback.md](robustness/013-wasm-fallback.md) |

### Data Integrity & Testing

| # | Standard | File |
|---|----------|------|
| **012** | Data Integrity | [data-integrity/012-data-integrity.md](data-integrity/012-data-integrity.md) |
| **016** | MCP Integration Testing | [testing/016-mcp-integration-testing.md](testing/016-mcp-integration-testing.md) |
| **017** | Dependency Validation | [dependencies/017-dependency-validation.md](dependencies/017-dependency-validation.md) |
| **019** | Code Analysis | [analysis/019-code-analysis.md](analysis/019-code-analysis.md) |
| **022** | Documentation Hygiene | [documentation/022-documentation-hygiene.md](documentation/022-documentation-hygiene.md) |
| **028** | Unified Test Pipeline | [testing/028-unified-test-pipeline.md](testing/028-unified-test-pipeline.md) |

---

## 📝 Standard Format

Each standard follows this structure:

1. **Title** - Clear, descriptive name
2. **Status** - Active / Deprecated / Draft
3. **Date** - Creation date
4. **Priority** - P0, P1, P2
5. **Problem** - What problem does this solve?
6. **Solution** - How is the problem solved?
7. **Implementation** - Code examples and patterns
8. **Testing** - Test cases and verification
9. **Related Standards** - Cross-references

---

## 🔗 Related Documentation

- [spec.md](../spec.md) - System specification
- [plan.md](../plan.md) - Project plan & roadmap
- [tasks.md](../tasks.md) - Current tasks
- [CHANGELOG.md](../../CHANGELOG.md) - Version history

---

**Last Updated:** May 19, 2026
**Total Standards:** 33