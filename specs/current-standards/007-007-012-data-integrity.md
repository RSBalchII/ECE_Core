# Standard 012: Data Integrity

**Status:** Active
**Date:** 2026-03-22
**Updated:** 2026-03-22 (Added Operation State Machine)
**Supersedes:** Standard 051 (Ephemeral Index)

## Context
Anchor Engine uses PGlite as an ephemeral index database and `mirrored_brain/` as a cleaned content cache. Corruption can accumulate from unclean shutdowns, transaction conflicts, and failed writes.

## Pain Points Fixed
- Commit `b2cdb89`: `mirrored_brain/` accumulated corrupted files (e.g., malformed package.json)
- Commit `3afec1d`: Transaction conflicts during concurrent ingestion and graph export
- Commit `3819e33`: Duplicate fix for transaction conflicts
- Various: Silent database write failures during heavy ingestion

## Requirements

### DATA-001: Ephemeral Database Wipe
1. Wipe `mirrored_brain/` and transient databases on every startup
2. Never trust persisted state from previous runs for ephemeral data structures
3. Prevents corruption accumulation from unclean shutdowns

```typescript
// In db.ts init()
if (shouldWipe) {
  // Remove database directory
  fs.rmSync(dbPath, { recursive: true, force: true });

  // Also wipe mirrored_brain
  const mirroredBrainPath = path.join(path.dirname(dbPath), 'mirrored_brain');
  if (fs.existsSync(mirroredBrainPath)) {
    const entries = fs.readdirSync(mirroredBrainPath);
    for (const entry of entries) {
      fs.rmSync(path.join(mirroredBrainPath, entry), { recursive: true, force: true });
    }
  }
}
```

### DATA-002: Operation State Machine

**Added 2026-03-22:** Heavy operations MUST use a state machine to prevent conflicts.

```typescript
// Engine operation states
type EngineState = 'idle' | 'ingesting' | 'searching' | 'exporting' | 'distilling';

// Global state tracker
const engineState: { current: EngineState; since: Date; operation?: string } = {
  current: 'idle',
  since: new Date()
};

// State transition function
function setEngineState(newState: EngineState, operation?: string): boolean {
  // Only allow transitions from idle, or to idle
  if (engineState.current !== 'idle' && newState !== 'idle') {
    console.warn(`[Engine] Cannot transition from ${engineState.current} to ${newState}`);
    return false;
  }
  
  engineState.current = newState;
  engineState.since = new Date();
  engineState.operation = operation;
  console.log(`[Engine] State: ${newState}${operation ? ` (${operation})` : ''}`);
  return true;
}

// Check before heavy operation
function canStartOperation(operation: EngineState): boolean {
  if (engineState.current !== 'idle') {
    return false;
  }
  return setEngineState(operation);
}

// Release state after operation
function releaseEngineState(): void {
  setEngineState('idle');
}
```

**Usage in endpoints:**

```typescript
// POST /v1/ingest
app.post('/v1/ingest', async (req, res) => {
  if (!canStartOperation('ingesting')) {
    return res.status(503).json({
      error: `Engine busy: ${engineState.current}`,
      retryAfter: 30
    });
  }
  
  try {
    await performIngestion(req.body);
  } finally {
    releaseEngineState();
  }
});

// GET /v1/graph/export
app.get('/v1/graph/export', async (req, res) => {
  if (!canStartOperation('exporting')) {
    return res.status(503).json({
      error: `Engine busy: ${engineState.current}`,
      retryAfter: 30
    });
  }
  
  try {
    await exportGraph();
  } finally {
    releaseEngineState();
  }
});
```

**State visibility in health endpoint:**

```typescript
// GET /health
app.get('/health', async (req, res) => {
  res.json({
    status: 'healthy',
    engineState: engineState.current,
    engineStateSince: engineState.since,
    currentOperation: engineState.operation
  });
});
```

### DATA-003: Transaction Conflict Prevention
1. Check if ingestion is active before running read-heavy operations
2. Return graceful error: "Ingestion in progress, try again later"
3. Prevents database lock conflicts

```typescript
// ✅ CORRECT: Check before heavy operation
if (systemStatus.isIngesting()) {
  return res.status(503).json({
    error: 'Ingestion in progress',
    retryAfter: systemStatus.estimatedCompletionTime()
  });
}

// ❌ WRONG: Blind operation that may conflict
const results = await db.query('SELECT * FROM atoms');
```

### DATA-004: Write Verification
1. Ingestion API must verify atoms were created
2. Return error count if writes fail
3. Log prominently if database write fails

```typescript
// Verify write succeeded
const insertedCount = result.rowCount;
if (insertedCount !== expectedCount) {
  console.error(`[Ingest] Write mismatch: expected ${expectedCount}, got ${insertedCount}`);
  return { success: false, error: 'Write verification failed' };
}
```

## Implementation Notes
- Database wipe in `engine/src/core/db.ts`
- Transaction management in `engine/src/core/db.ts` (beginTransaction/commit/rollback)
- Status tracking in `engine/src/services/ingest/watchdog.ts`
- State machine in `engine/src/services/system-status.ts` (to be implemented)