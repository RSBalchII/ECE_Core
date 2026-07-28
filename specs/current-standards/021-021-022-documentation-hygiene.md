# Standard 022: Documentation Hygiene

**Status:** ✅ Active | **Priority:** P0 | **Created:** 2026-03-26

---

## 🎯 Problem Statement

The Anchor Engine project has excellent documentation, but suffers from:

1. **Documentation Drift** - Same issues fixed multiple times across commits
2. **Fragmentation** - 220+ markdown files scattered across the project
3. **Duplication** - Multiple TROUBLESHOOTING.md, SETUP.md, TESTING.md files
4. **Archive Bloat** - 136 archived standards + 20 current = hard to find what's current
5. **Root Pollution** - .md files appearing in forbidden directories (benchmarks/, tests/, scripts/)

**Recent Examples (Last 100 Commits):**
- Configuration management fixed 3+ times (user_settings.json consolidation in 0e86af7)
- GitHub PAT authentication added across 4 commits (e11d197, 22d0fec, 7c7b34f, b8314de)
- Path centralization done in 6cec1b1, but pathManager.ts still had wrong paths
- MCP integration fixes across 5+ commits

**Root Cause:** No enforcement mechanism for documentation location and no cross-reference system to check if a problem was already solved.

---

## ✅ Solution: Documentation Hygiene Protocol

### Rule 1: Allowed Directories (MANDATORY)

**ONLY create documentation in:**

```
✅ ALLOWED:
├── docs/                    # User-facing documentation
│   ├── setup/              # Installation guides
│   ├── api/                # API reference
│   ├── guides/             # How-to guides
│   ├── troubleshooting/    # Troubleshooting
│   └── technical/          # Deep-dives
│
├── specs/
│   ├── current-standards/  # Active standards (001-022)
│   └── proposals/          # Proposed standards
│
└── [PACKAGE]/README.md     # Package READMEs only (mcp-server/, packages/*)
```

**NEVER create documentation in:**
```
❌ FORBIDDEN:
├── *.md (root level, except README, CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT)
├── benchmarks/*.md
├── tests/*.md
├── scripts/*.md
├── engine/docs/*.md
├── .ai/, .cursor/, .jules/ (hidden directories)
└── Any subdirectory not listed in ALLOWED
```

**Enforcement:**
- CI check for .md files in forbidden directories
- Pre-commit hook warns on forbidden paths
- AI assistants (.ai-instructions.md) must enforce this rule

---

### Rule 2: Cross-Reference Check (BEFORE Writing)

**Before creating ANY documentation:**

```bash
# 1. Search for existing content
grep -ri "your topic" docs/ specs/current-standards/

# 2. Check recent commits (last 100)
git log --oneline -100 | grep -i "your topic"

# 3. Check if standard already covers it
ls specs/current-standards/ | grep -i "keyword"
```

**If found:**
- ✅ Update existing doc (don't create new)
- ✅ Link to existing doc (don't duplicate)
- ✅ Add to "Related" section of existing doc

**If not found:**
- ✅ Create in correct directory (Rule 1)
- ✅ Add cross-references at bottom
- ✅ Update docs/INDEX.md if needed

---

### Rule 3: Pain Point → Standard Pipeline

**When fixing a problem that took >3 commits or >2 hours:**

1. **Document the pain point** (in this standard's appendix)
2. **Create or update a standard** (specs/current-standards/)
3. **Add test coverage** (if applicable)
4. **Update CHANGELOG.md**

**Example:**
```
Pain Point: GitHub PAT authentication took 4 commits to implement correctly
↓
Standard: 015-configuration-management.md (updated)
↓
Test: tests/unit/github-pat-flow.test.ts
↓
Changelog: v4.9.6 - GitHub PAT authentication
```

**Template for Pain Point Entry:**
```markdown
### [Pain Point Title]
- **Date:** YYYY-MM-DD
- **Commits:** [list commit hashes]
- **Time Spent:** X hours
- **Root Cause:** [why it happened]
- **Solution:** [what fixed it]
- **Prevention:** [standard/test added]
- **Cross-Reference:** [related standards]
```

---

### Rule 4: Archive Policy

**Automatic Archival:**
- Standards inactive for 6+ months → Move to `specs/archive-standards/history/`
- Superseded standards → Keep only latest + link to archive
- Legacy architecture (CozoDB, old systems) → `specs/archive-legacy/`

**Current Standards Limit:**
- Maximum 30 active standards
- If exceeded, archive oldest inactive standard
- Index in `specs/README.md` (not in docs/)

**Archive Structure:**
```
specs/archive-standards/
├── history/              # Numbered standards (059-200+)
├── legacy-archive/       # Pre-standard docs
└── redundant-YYYY-MM/    # Redundant docs by month
```

---

### Rule 5: Documentation Synthesis

**Quarterly Documentation Audit:**

1. **Consolidate duplicates**
   - Merge all TESTING.md → docs/testing/TESTING.md
   - Merge all TROUBLESHOOTING.md → docs/troubleshooting/TROUBLESHOOTING.md
   - Merge all SETUP.md → docs/setup/SETUP.md

2. **Update cross-references**
   - Check all links in docs/INDEX.md
   - Remove dead links
   - Add "Related Docs" sections

3. **Archive old content**
   - Move standards inactive >6 months
   - Remove redundant files
   - Update CHANGELOG.md with consolidation

**Checklist:**
- [ ] No .md files in forbidden directories
- [ ] All standards <6 months old or marked "active"
- [ ] docs/INDEX.md up to date
- [ ] No duplicate troubleshooting guides
- [ ] Pain point appendix updated

---

## 📊 Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Active standards | ≤30 | 22 | ✅ |
| Root .md files | ≤6 | 12 | ❌ |
| Forbidden .md files | 0 | 15+ | ❌ |
| Duplicate guides | 0 | 5+ | ❌ |
| Cross-references | 100% | ~50% | ❌ |

**Action Items:**
1. Move root .md files to docs/ (except allowed 6)
2. Consolidate duplicate guides
3. Add cross-references to all standards
4. Archive standards inactive >6 months

---

## 🔗 Related Standards

- **Standard 015:** Configuration Management (updated with PAT flow)
- **Standard 018:** Configuration Validation
- **Standard 020:** Ephemeral Database
- **Standard 021:** Pointer-Only Storage

---

## 📝 Appendix: Pain Point Log

### Configuration Drift (2026-03-25)
- **Commits:** 0e86af7, d6ec794, f960f8b, +6 more
- **Time Spent:** 4 hours
- **Root Cause:** API key, version, paths scattered across config files
- **Solution:** Single Source of Truth - user_settings.json (0e86af7)
- **Prevention:** Standard 015 updated, paths.ts reads from user_settings.json
- **Cross-Reference:** Standards 015, 018, 022

### GitHub PAT Authentication (2026-03-26)
- **Commits:** e11d197, 22d0fec, 7c7b34f, b8314de
- **Time Spent:** 2 hours
- **Root Cause:** Token flow not documented, UI ↔ API ↔ Service mismatch
- **Solution:** localStorage caching, X-GitHub-Token header, auto-generated buckets
- **Prevention:** This standard (022), pain point logged
- **Cross-Reference:** Standards 011 (security), 015 (config)

### Path Manager Bug (2026-03-26)
- **Commits:** 6cec1b1 (path centralization), +3 fixes
- **Time Spent:** 1.5 hours
- **Root Cause:** pathManager.getNotebookDir() used `../..` instead of `..`
- **Solution:** Fixed path-manager.ts, added PATHS.DISTILLS_DIR
- **Prevention:** Paths now configurable in user_settings.json
- **Cross-Reference:** Standard 015, 022

### Distill File Read Error (2026-03-26)
- **Commits:** +4 fixes
- **Time Spent:** 1 hour
- **Root Cause:** radial-distiller-v2.ts writes to `notebook/distills/`, but /v1/files/read looked in `inbox/distilled/`
- **Solution:** Updated system.ts to use PATHS.DISTILLS_DIR, switched to radial-distiller-v2
- **Prevention:** All paths now use PATHS.* constants from paths.ts
- **Cross-Reference:** Standard 022, 015

### Old UI Build Contamination (2026-03-26)
- **Commits:** Multiple rebuilds required
- **Time Spent:** 30 minutes
- **Root Cause:** `packages/anchor-ui/dist` regenerated by `pnpm build:all`, old Vite build overriding single-file UI
- **Solution:** 
  1. Removed `anchor-ui build` from build:all script
  2. Added `clean:ui-dist` post-build step
  3. Added `packages/anchor-ui/dist/` to .gitignore
- **Prevention:** Build script now auto-deletes UI dist folder
- **Cross-Reference:** Standard 022 (allowed directories rule)

---

## ✅ Enforcement

**For AI Assistants:**
- Read `.ai-instructions.md` before ANY documentation changes
- Check this standard (022) before creating new docs
- Search `grep -ri` for existing content before writing

**For Humans:**
- Pre-commit hook checks forbidden directories
- PR template asks: "Does this already exist in docs/ or specs/?"
- Code review checks for cross-references

**For CI:**
- Fail on .md files in forbidden directories
- Warn on standards >6 months without "active" tag
- Check docs/INDEX.md links on build

---

**Last Updated:** 2026-03-26  
**Next Review:** 2026-06-26 (quarterly audit)  
**Owner:** Project Maintainers
