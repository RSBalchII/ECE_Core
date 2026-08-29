# Documentation Policy

## 1. Core Philosophy

Documentation in Anchor Engine must be **concise**, **accurate**, and **maintainable**. We prioritize high-signal technical writing over verbose explanations.

**Guiding Principles:**
- **Single Source of Truth:** Each topic should have one authoritative location
- **Minimal Root:** The project root contains only essential files
- **Clear Separation:** `specs/` for technical specifications, `docs/` for user-facing guides
- **Actionable Content:** Documentation should drive implementation and testing

---

## 2. Document Locations

### 2.1 Root Directory (`/`)

**ALLOWED Files (Only):**
| File | Purpose |
|------|---------|
| `README.md` | Project overview, quickstart, API reference, architecture |
| `CHANGELOG.md` | Version history and release notes |
| `LICENSE` | License file (AGPL-3.0) |
| `.gitignore` | Git ignore patterns |
| `package.json` | Package configuration |
| `CITATION.cff` | Citation metadata (version, authors) |
| `paper.bib` | Academic bibliography (BibTeX) |
| `Dockerfile`, `docker-compose.yml` | Containerized deployment |
| `user_settings.json.template` | Configuration template (runtime copy lives in `.anchor/`) |

**PROHIBITED in Root:**
- Phase completion reports
- Implementation summaries
- Git operation logs
- Temporary documentation files
- Any other `.md` files not listed above

### 2.2 Specs Directory (`/specs/`)

**Core Files (Only):**
| File | Purpose |
|------|---------|
| `spec.md` | Main technical specification with architecture diagrams |
| `plan.md` | Development roadmap and phased implementation |
| `tasks.md` | Current implementation tasks and priorities |
| `doc_policy.md` | This documentation policy |
| `shutdown-cleanup.md` | Shutdown and cleanup operational procedure |

**Subdirectories:**
- `current-standards/` - 39 active architecture standards (001-039), indexed by `000-STANDARDS_INDEX.md`

Historical standard entries are preserved as `[Standard NNN]` sections in `CHANGELOG.md`.

**PROHIBITED in specs root:**
- Duplicate documentation already in README
- Phase reports or implementation logs
- Redundant standards documentation

### 2.3 Docs Directory (`/docs/`)

**Core Focus Areas:**

| Area | Files | Purpose |
|------|-------|---------|
| **Whitepaper** | `whitepaper.md`, `paper.md`, `star-whitepaper.tex`, `BIBLIOGRAPHY.bib` | STAR algorithm research and academic papers |
| **API Reference** | `mcp-setup.md`, root `README.md` (MCP Integration) | Tool surface, endpoints, and configuration |
| **Deployment** | `CROSS_PLATFORM_SETUP.md`, `INSTALL.md`, root `Dockerfile` / `docker-compose.yml` | Installation and deployment across platforms |
| **Standards** | `../specs/current-standards/000-STANDARDS_INDEX.md` | Active standards index (001–039) |
| **Troubleshooting** | `troubleshooting/issues-log.md`, `testing/smoke-test-watchdog-fix.md` | Durable issue tracker and known-issue resolutions |
| **Integration** | `integrations/`, `mcp-agent.md`, `mcp-setup.md` | External integrations and contribution guidelines |

**PROHIBITED in docs root:**
- Temporary files
- Unfinished drafts
- Phase-specific reports

---

## 3. Documentation Standards

### 3.1 README.md Structure

```markdown
# Anchor Engine

## Quick Start (5-minute setup)
## Core Features
## Architecture Overview
## API Reference (summary)
## Configuration Guide
## Performance Benchmarks
## Security Hardening
## Contributing
## License
```

### 3.2 CHANGELOG.md Format

- Follow [Keep a Changelog](https://keepachangelog.com/) format
- Semantic versioning (MAJOR.MINOR.PATCH)
- Group changes by: Added, Changed, Deprecated, Removed, Fixed, Security
- Include date and version number
- Link to GitHub releases when applicable

### 3.3 Standards (specs/current-standards/)

- Numbered format: `XXX-title.md`
- Include: Purpose, Problem Statement, Solution, Implementation Details, Testing
- Reference related standards
- Include code examples where applicable

---

## 4. Prohibited Documentation Patterns

**DO NOT CREATE in Root:**
- ❌ Phase completion reports (PHASE_1_COMPLETE.md, etc.)
- ❌ Implementation update logs (BATCHING_UPDATE.md, etc.)
- ❌ Git operation logs (GIT_PUSH_COMPLETE.md, etc.)
- ❌ Consolidation summaries (DOCS_CONSOLIDATION_SUMMARY.md, etc.)
- ❌ Standard implementation reports (STANDARD_109_IMPLEMENTATION.md, etc.)

**Instead, update:**
- ✅ `README.md` with new features and architecture
- ✅ `CHANGELOG.md` with version changes
- ✅ `specs/current-standards/` with architecture standards
- ✅ `specs/spec.md` with architectural changes
- ✅ `docs/` with user-facing guides

---

## 5. Runtime Object Storage

**⚠️ CRITICAL: All runtime objects are stored in `$home/.anchor`**

This includes:
- **Logs:** `.anchor/logs/` (search logs, distillation logs, engine logs)
- **Database:** `.anchor/context_data/` (PGlite database)
- **Distillation outputs:** `.anchor/notebook/distills/` (YAML/JSON summaries)
- **Test outputs:** `.anchor/test-output/` (test result files)
- **Audit files:** `.anchor/logs/.<hash>-audit.json`
- **Session data:** `.anchor/sessions/`
- **Inbox files:** `.anchor/inbox/`, `.anchor/external-inbox/`
- **Mirrored brain:** `.anchor/mirrored_brain/`
- **User settings:** `.anchor/user_settings.json` (runtime configuration - NEVER in project root)

**Never assume files are in the project root or `engine/` directory.** Always check `.anchor/` first for runtime data.

---

## 5. Maintenance Guidelines

### 5.1 Before Merging PR

- [ ] Verify no prohibited `.md` files in root
- [ ] Ensure all new features documented in README or CHANGELOG
- [ ] Update relevant standards in `specs/current-standards/`
- [ ] Remove temporary documentation files after integration
- [ ] **Verify user_settings.json is NOT in project root** (should be in `.anchor/user_settings.json`)

### 5.2 Automated Checks (Future CI/CD)

- Reject PRs with prohibited `.md` files in root
- Verify `CHANGELOG.md` updated for version changes
- Check `README.md` includes new features
- Validate documentation links and cross-references

### 5.3 Content Ownership

| Domain | Owner | Primary Location |
|--------|-------|------------------|
| **Architecture** | Architecture Team | `specs/spec.md`, `specs/current-standards/` |
| **User Guides** | Documentation Team | `docs/` (whitepaper, guides, integration) |
| **API Reference** | Development Team | `docs/mcp-setup.md`, `README.md` (MCP Integration) |
| **Deployment** | DevOps Team | `Dockerfile`, `docker-compose.yml`, `docs/CROSS_PLATFORM_SETUP.md` |
| **Testing** | QA Team | `tests/`, `docs/testing/`, `docs/streamlined-testing.md` |

---

## 6. Migration Path

### 6.1 Root-to-Docs Migration

Move root-level documentation to appropriate `docs/` subdirectories:

| Root File | Target Location | Status |
|-----------|-----------------|--------|
| `FRICTIONLESS_SPEC.md` | `docs/guides/frictionless-spec.md` | ✅ |
| `MCP_AGENT_SETUP.md` | `docs/integrations/mcp-agent.md` | ✅ |
| `RECURSIVE_SEARCH_FALLBACKS.md` | `docs/technical/recursive-search.md` | ✅ |
| `PAIN_POINTS_DOCUMENTATION.md` | `docs/guides/pain-points.md` | ✅ |
| `CLAW-CODE-INTEGRation.md` | `docs/integrations/claw-integration.md` | ✅ |

### 6.2 Specs Consolidation

**Current State:**
- `specs/` contains the core specification files plus an operational procedure (`shutdown-cleanup.md`)
- `specs/current-standards/` has 39 active standards (001-039), indexed by `000-STANDARDS_INDEX.md`
- Historical standard entries are preserved as `[Standard NNN]` sections in `CHANGELOG.md`

**Target State:**
- No additional `.md` files in `specs/` root beyond the listed operational procedures
- All standards properly organized in subdirectories
- Clear separation between active and historical content

---

## 7. Rationale

**Why this policy?**
1. **Prevents Documentation Sprawl:** Clear boundaries prevent uncontrolled growth
2. **Ensures Single Source of Truth:** Each topic has one authoritative location
3. **Makes Finding Information Easier:** Users know where to look for specific content
4. **Reduces Maintenance Burden:** Clear ownership and structure
5. **Keeps Repository Clean and Professional:** Root remains focused on essentials

**What to do with implementation notes?**
1. Update relevant standard in `specs/current-standards/` (if architectural)
2. Add to `CHANGELOG.md` (if user-facing change)
3. Add to `README.md` (if new feature or major update)
4. Archive to `docs/` (if detailed guidance needed)
5. Delete temporary notes after integration

---

## 8. Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-04-09 | Restructured for clarity, consolidated specs and docs |
| 1.0 | 2026-02-20 | Initial documentation policy |

---

**Last Updated:** August 22, 2026
**Version:** 2.1
**Status:** ✅ Active
