# Anchor Engine - Documentation Index

**Version:** 5.2.0 | **Updated:** August 22, 2026 | **Status:** ✅ Production Ready

---

## 📚 Quick Navigation

### Getting Started
- **[README.md](../README.md)** - Project overview, quick start, usage guide
- **[QUICK_START.md](QUICK_START.md)** - Five-minute setup walkthrough
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history (latest: v5.2.0)
- **[CONTRIBUTING.md](integrations/CONTRIBUTING.md)** - How to contribute

### Core Documentation
- **[whitepaper.md](whitepaper.md)** - STAR algorithm whitepaper
- **[paper.md](paper.md)** - Academic paper
- **[STAR_Whitepaper_Executive.md](STAR_Whitepaper_Executive.md)** - Executive summary of the whitepaper
- **[code-patterns.md](code-patterns.md)** - Code patterns
- **[design-patterns.md](design-patterns.md)** - Design patterns in use

### Technical Reference
- **[pglite-quick-reference.md](pglite-quick-reference.md)** - PGlite quick reference
- **[star-algebra-reference.md](star-algebra-reference.md)** - STAR algebra reference
- **[TAXONOMY.md](TAXONOMY.md)** - Compound/tag taxonomy
- **[specs/spec.md](../specs/spec.md)** - System specification with diagrams

### Architecture & Standards
- **[specs/plan.md](../specs/plan.md)** - Development roadmap
- **[specs/tasks.md](../specs/tasks.md)** - Current tasks
- **[specs/doc_policy.md](../specs/doc_policy.md)** - Documentation policy
- **[specs/shutdown-cleanup.md](../specs/shutdown-cleanup.md)** - Shutdown and cleanup procedure
- **[specs/current-standards/000-STANDARDS_INDEX.md](../specs/current-standards/000-STANDARDS_INDEX.md)** - Active standards index (001–039)

### Development & Testing
- **[engine/src/README.md](../engine/src/README.md)** - Source code overview
- **[mcp-server/README.md](../mcp-server/README.md)** - MCP server integration
- **[streamlined-testing.md](streamlined-testing.md)** - Streamlined testing guide
- **[test-logging-guide.md](test-logging-guide.md)** - Test logging conventions
- **[testing/SMOKE_TEST_PLAN.md](testing/SMOKE_TEST_PLAN.md)** - Smoke test plan (live-fire)
- **[testing/LIVE-FIRE-TEST-SUITE.md](testing/LIVE-FIRE-TEST-SUITE.md)** - Live-fire test suite

### Integration & Operations
- **[mcp-agent.md](mcp-agent.md)** - MCP agent integration
- **[mcp-setup.md](mcp-setup.md)** - MCP setup and tool surface (API reference)
- **[CROSS_PLATFORM_SETUP.md](CROSS_PLATFORM_SETUP.md)** - Cross-platform installation notes
- **[INSTALL.md](INSTALL.md)** - Installation guide
- **[troubleshooting/issues-log.md](troubleshooting/issues-log.md)** - Durable issue tracker

---

## 🎯 Documentation by Use Case

### "I want to install and run Anchor Engine"
→ Start with **[README.md](../README.md)** (Quick Start) or **[QUICK_START.md](QUICK_START.md)**; see **[INSTALL.md](INSTALL.md)** and **[CROSS_PLATFORM_SETUP.md](CROSS_PLATFORM_SETUP.md)** for platform-specific setup

### "I need API documentation"
→ Read the **MCP Integration** section of **[README.md](../README.md)** and **[mcp-setup.md](mcp-setup.md)** - tool surface, endpoints, and configuration

### "I want to deploy to production"
→ Use the root **Dockerfile** / **docker-compose.yml**, or follow **[CROSS_PLATFORM_SETUP.md](CROSS_PLATFORM_SETUP.md)**

### "Something's not working"
→ Check **[troubleshooting/issues-log.md](troubleshooting/issues-log.md)** (durable issue tracker) and **[testing/smoke-test-watchdog-fix.md](testing/smoke-test-watchdog-fix.md)**

### "I need to understand the system architecture"
→ Study **[specs/spec.md](../specs/spec.md)** - System specification with diagrams

### "I'm researching the theory behind Anchor Engine"
→ Read **[whitepaper.md](whitepaper.md)**, **[paper.md](paper.md)**, and **[STAR_Whitepaper_Executive.md](STAR_Whitepaper_Executive.md)**

### "I want to understand the search algorithm"
→ See **[specs/current-standards/032-031-search-algorithms-comprehensive.md](../specs/current-standards/032-032-031-search-algorithms-comprehensive.md)** and **[whitepaper.md](whitepaper.md)**

### "How does distillation work?"
→ Read **[specs/current-standards/015-015-distillation.md](../specs/current-standards/015-015-distillation.md)**

### "I want to contribute code"
→ Start with **[CONTRIBUTING.md](integrations/CONTRIBUTING.md)** and **[engine/src/README.md](../engine/src/README.md)**

### "I want to connect via MCP"
→ See **[mcp-agent.md](mcp-agent.md)** and **[mcp-setup.md](mcp-setup.md)**

### "I need to write tests"
→ Follow **[streamlined-testing.md](streamlined-testing.md)**, **[test-logging-guide.md](test-logging-guide.md)**, and **[testing/SMOKE_TEST_PLAN.md](testing/SMOKE_TEST_PLAN.md)**

---

## 📊 Key Metrics (v5.2.0)

| Metric | Value | Status |
|--------|-------|-------|
| **Active Standards** | 39 (001–039) | ✅ Indexed in `specs/current-standards/` |
| **Historical Standards** | Preserved as `[Standard NNN]` entries in CHANGELOG.md | ✅ No separate archive |
| **Documentation Files** | ~24 .md files under `docs/` | ✅ Aligned to actual structure |
| **Context Retrieval** | 618k chars (v5.0.0 baseline) | ⏳ Pending re-benchmark after v5.2 milestone |
| **Memory Peak** | 510MB (v5.0.0 baseline) | ⏳ Pending re-benchmark after v5.2 milestone |

---

## 🗂️ Document Structure

```
anchor-engine-node/
├── README.md                      # Start here - overview & quick start
├── CHANGELOG.md                   # Version history (latest: v5.2.0)
├── CITATION.cff                   # Citation metadata
├── paper.bib                      # Academic bibliography
├── Dockerfile / docker-compose.yml  # Containerized deployment
├── user_settings.json.template    # Configuration template (runtime copy in ~/.anchor/)
│
├── docs/                          # User-facing documentation (~24 .md files)
│   ├── QUICK_START.md             # Five-minute setup walkthrough
│   ├── INSTALL.md                 # Installation guide
│   ├── CROSS_PLATFORM_SETUP.md    # Cross-platform notes
│   ├── whitepaper.md              # STAR algorithm whitepaper
│   ├── paper.md                   # Academic paper (arXiv)
│   ├── star-whitepaper.tex        # LaTeX whitepaper source
│   ├── BIBLIOGRAPHY.bib           # Academic bibliography
│   ├── RELATED_WORK.tex           # Related work documentation
│   ├── STAR_Whitepaper_Executive.md # Executive summary
│   ├── star-algebra-reference.md  # STAR algebra reference
│   ├── pglite-quick-reference.md  # PGlite quick reference
│   ├── TAXONOMY.md                # Compound/tag taxonomy
│   ├── code-patterns.md           # Code patterns
│   ├── design-patterns.md         # Design patterns
│   ├── mcp-agent.md               # MCP agent integration
│   ├── mcp-setup.md               # MCP setup & tool surface
│   ├── streamlined-testing.md     # Streamlined testing guide
│   ├── test-logging-guide.md      # Test logging conventions
│   │
│   ├── integrations/              # Community guidelines
│   │   ├── CODE_OF_CONDUCT.md
│   │   └── CONTRIBUTING.md
│   ├── testing/                   # Live-fire & smoke tests
│   │   ├── SMOKE_TEST_PLAN.md
│   │   ├── LIVE-FIRE-TEST-SUITE.md
│   │   └── smoke-test-watchdog-fix.md
│   ├── troubleshooting/           # Durable issue tracker
│   │   └── issues-log.md
│   └── handoffs/                  # Session handoff notes
│
├── specs/
│   ├── spec.md                    # System specification
│   ├── plan.md                    # Development roadmap
│   ├── tasks.md                   # Current tasks
│   ├── doc_policy.md              # Documentation policy
│   ├── shutdown-cleanup.md        # Shutdown & cleanup procedure
│   └── current-standards/         # Active standards (001–039) + 000 index
│
├── engine/                        # Engine source
│   └── src/README.md              # Source code overview
├── mcp-server/                    # MCP server
│   └── README.md                  # MCP server documentation
└── tests/                         # Test suites (vitest, e2e, live-fire)
    └── benchmarks/                # Benchmarking framework
```

---

## 🎓 Learning Path

### Beginner (Just Getting Started)
1. **[README.md](../README.md)** - Installation & first query
2. **[QUICK_START.md](QUICK_START.md)** - Five-minute setup walkthrough
3. **[CHANGELOG.md](../CHANGELOG.md)** - Recent features

### Intermediate (Understanding the System)
1. **[specs/spec.md](../specs/spec.md)** - Full system specification
2. **[whitepaper.md](whitepaper.md)** - Search algorithm & theory
3. **[specs/current-standards/015-015-distillation.md](../specs/current-standards/015-015-distillation.md)** - Radial Distillation (all modes)
4. **[engine/src/README.md](../engine/src/README.md)** - Source overview

### Advanced (Deep Dive)
1. **[whitepaper.md](whitepaper.md)** and **[paper.md](paper.md)** - Theoretical foundation
2. **[specs/current-standards/000-STANDARDS_INDEX.md](../specs/current-standards/000-STANDARDS_INDEX.md)** - All active standards
3. Root **Dockerfile** / **docker-compose.yml** - Production deployment

### Contributor (Writing Code)
1. **[CONTRIBUTING.md](integrations/CONTRIBUTING.md)** - Contribution guidelines
2. **[engine/src/README.md](../engine/src/README.md)** - Source structure
3. **[streamlined-testing.md](streamlined-testing.md)** and **[test-logging-guide.md](test-logging-guide.md)** - Testing requirements
4. **[specs/current-standards/000-STANDARDS_INDEX.md](../specs/current-standards/000-STANDARDS_INDEX.md)** - Architecture standards

---

## 🔬 Recent Updates (v5.2.0 - August 22, 2026)

### Documentation Alignment (August 22, 2026)
- **INDEX & doc_policy realignment:** All documentation links now resolve to actual files; standards count corrected to 39 (001–039); `archive-legacy/` references removed (historical entries live in CHANGELOG.md)
- **Version metadata alignment:** package.json, engine/package.json, CITATION.cff, and user_settings.json.template aligned to v5.2.0 (runtime version was already 5.2.0 via database-backed settings)

### Smoke Test Remediation & v5.2 Milestone (August 19–21, 2026)
- **Standard 110 path centralization:** Runtime objects centralized under `~/.anchor/` (see specs/shutdown-cleanup.md and troubleshooting/issues-log.md)
- **Standards updates:** 011 (heap overflow constraint), 022 (OPS-005 crash observability), 028 (safeDate rule), 036 (scope expansion)
- **Durable issue tracker established:** docs/troubleshooting/issues-log.md

### Documentation Consolidation (May 20, 2026)
- **Settings Consolidation:** Merged 5 separate settings files into a single consolidated settings & configuration reference
- **Moved Integration Docs:** CODE_OF_CONDUCT.md and CONTRIBUTING.md relocated to `docs/integrations/` directory
- **Flattened Structure:** Removed all subdirectories, consolidated ~20 .md files in `docs/`

---

## 📁 Documentation Categories

### User-Facing
| Document | Purpose |
|----------|---------|
| README.md | Overview & quick start |
| QUICK_START.md | Five-minute setup walkthrough |
| INSTALL.md / CROSS_PLATFORM_SETUP.md | Installation across platforms |
| troubleshooting/issues-log.md | Durable issue tracker |

### Developer-Facing
| Document | Purpose |
|----------|---------|
| code-patterns.md | Code patterns |
| design-patterns.md | Design patterns |
| streamlined-testing.md | Testing guide |
| test-logging-guide.md | Test logging conventions |

### Academic/Research
| Document | Purpose |
|----------|---------|
| whitepaper.md | STAR algorithm paper |
| paper.md | Academic paper (arXiv) |
| BIBLIOGRAPHY.bib / star-whitepaper.tex | Bibliography & LaTeX source |

### Integration
| Document | Purpose |
|----------|---------|
| mcp-agent.md | MCP agent integration |
| mcp-setup.md | MCP setup & tool surface |
| integrations/CONTRIBUTING.md | Contribution guidelines |

---

## 🔗 External Resources

- **GitHub Repository:** https://github.com/RSBalchII/anchor-engine-node
- **License:** AGPL-3.0
- **NPM Packages:** @rbalchii/* (native modules)
- **DOI:** https://doi.org/10.5281/zenodo.18841399

---

## 📞 Support & Contribution

### Getting Help
- Check **[troubleshooting/issues-log.md](troubleshooting/issues-log.md)** for known issues and fixes
- Review **[specs/spec.md](../specs/spec.md)** for system understanding
- Read **[CHANGELOG.md](../CHANGELOG.md)** for recent fixes

### Contributing
1. Read **[CONTRIBUTING.md](integrations/CONTRIBUTING.md)** for guidelines
2. Review **[engine/src/README.md](../engine/src/README.md)** for source structure
3. Follow **[specs/current-standards/000-STANDARDS_INDEX.md](../specs/current-standards/000-STANDARDS_INDEX.md)** for architecture standards
4. Run the test suite per **[streamlined-testing.md](streamlined-testing.md)** before submitting

---

**Last Updated:** August 22, 2026
**Version:** 5.2.0
**Status:** ✅ Production Ready
