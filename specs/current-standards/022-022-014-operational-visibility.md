# Standard 014: Operational Visibility

**Status:** Active
**Date:** 2026-03-22
**Supersedes:** N/A

## Context
Anchor Engine runs as a background service. Operators need visibility into startup status, health, and ongoing operations for debugging and monitoring.

## Pain Points Fixed
- Commit `dc072f9`: No startup confirmation made it unclear if engine started
- Commit `7ef1bd1`: No health endpoint for Docker health checks
- Commit `bbc7d04`: No ingestion progress tracking
- Commit `bbc7d04`: No agent discovery for multi-agent setups

## Requirements

### OPS-001: Startup Banner
Every service must print a startup banner showing:
- Version
- Database status (atom count)
- Watchdog status (paths being watched)
- API key status
- Health endpoint URL
- Startup time

```
⚓ Anchor Engine v4.9.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Database: 30,922 atoms
✅ Watchdog: active, watching 3 paths
✅ API key: set
✅ Health: http://localhost:3161/health
⏱️  Startup complete in 7.4s
```

### OPS-002: Health Endpoint
1. `GET /health` must return 200 healthy or 503 unhealthy
2. Verify database connectivity
3. Check critical directories exist
4. Docker health check compatible

```json
// Response
{
  "status": "healthy",
  "timestamp": "2026-03-22T05:32:31.839Z",
  "message": "Anchor Context Engine is running and database is responsive"
}
```

### OPS-003: Progress Tracking
1. Long operations must report progress
2. `GET /v1/ingest/status` returns current operation
3. Include files processed/total
4. Include estimated time remaining for large operations

```json
// Response
{
  "active": true,
  "state": "ingesting",
  "currentFile": "large-file.jsonl",
  "processed": 45,
  "total": 100,
  "atomsCreated": 1234,
  "startedAt": "2026-03-22T05:30:00.000Z",
  "queueDepth": 5
}
```

### OPS-004: Agent Discovery
1. `GET /v1/agent/discover` returns detected AI agents
2. Auto-detect common agent chat directories
3. Show watch status for each agent
4. Enable easy multi-agent setup

```json
// Response
{
  "status": "success",
  "count": 2,
  "agents": [
    {
      "id": "qwen",
      "name": "Qwen Code",
      "path": "/home/user/.qwen/chats",
      "sessionCount": 18,
      "isWatched": true
    },
    {
      "id": "claude",
      "name": "Claude",
      "path": "/home/user/.claude/chats",
      "sessionCount": 5,
      "isWatched": false
    }
  ]
}
```

## Implementation Notes
- Startup banner in `engine/src/utils/startup-banner.ts`
- Health endpoint in `engine/src/routes/health.ts`
- Ingestion status in `engine/src/routes/v1/ingest.ts`
- Agent discovery in `engine/src/routes/v1/agent.ts`