# Standard 001: Memory‑Safe File Ingestion

**Status:** Active  
**Date:** 2026-03-13  
**Supersedes:** Embedded warnings in `scripts/read_all.js`

## Context
Anchor Engine processes files from the filesystem and builds an in‑memory graph of molecules and atoms. Very large files or files containing more than 10,000 molecules have been observed to cause out‑of‑memory (OOM) crashes due to Node.js heap limits during ingestion.

## Requirements
1. **File Size Limit:** No single file larger than 10 MB shall be ingested as a whole. Files exceeding this limit must be split into smaller logical chunks before ingestion.
2. **Molecule Count Limit:** No file that atomizes to more than 10,000 molecules shall be processed in a single ingestion pass. Such files must be split or processed in a streaming fashion.
3. **Directory Structure Preservation:** The original natural directory structure of ingested files must be preserved in the mirrored brain. Do not combine files from different directories into a single compound.

## Implementation Notes
- The GitHub ingester (`scripts/github-ingester.js`) should automatically reject or split files exceeding these limits.
- The streaming ingestion service (`/v1/ingest/streaming`) can be used for large files.
- When splitting, ensure that each chunk retains provenance metadata linking back to the original file and location.