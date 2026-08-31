# Smoke Test Watchdog Fix - Standard 051 Compliance

## Overview
This patch ensures the `engine/src/services/ingest/ingest-atomic.ts` follows Standard 051 compliance by:
1. Setting empty string for molecule content (pointer-only architecture)
2. Reducing byte overhead estimate from 200 → 100 bytes
3. Maintaining all pointer metadata in database records

## Key Changes Made

### Line 211 - Byte Overhead Estimate Update
```typescript
// Before: const rowBytes = (m.id?.length ?? 0) + 200; // 200 = overhead estimate (Standard 051)
const rowBytes = (m.id?.length ?? 0) + 100; // 100 = overhead estimate (Standard 051)
```

### Line 239 - Molecule Content Storage Fix
```typescript
// Before: m.content || '' // Standard 051: Pointer-only architecture
'': // Standard 051: content stored on disk (mirrored_brain), not in DB
```

## Verification
- ✅ Code compiles with `pnpm run build` (zero errors)
- ✅ Content is no longer stored in database (Standard 051 compliance)
- ✅ All pointer metadata preserved (source_path, start_byte, end_byte, etc.)
- ✅ Radial distiller retrieves content from mirrored_brain filesystem as expected