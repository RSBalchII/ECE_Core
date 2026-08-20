import type { Application, Request, Response } from 'express';
import { db } from '../../core/db.js';

let searchCount = 0;
let ingestCount = 0;
const startTime = Date.now();

export function incrementSearchCount() { searchCount++; }
export function incrementIngestCount() { ingestCount++; }

export function setupStatsRoutes(app: Application) {
  app.get('/v1/stats', async (_req: Request, res: Response) => {
    try {
      const uptimeMs = Date.now() - startTime;
      const memUsage = process.memoryUsage();

      let moleculeCount = 0;
      let atomCount = 0;
      let distillCount = 0;

      try {
        const molResult = await db.run('SELECT COUNT(*) as count FROM molecules');
        moleculeCount = parseInt(molResult.rows?.[0]?.count || '0', 10);
      } catch { /* table may not exist */ }

      try {
        const atomResult = await db.run('SELECT COUNT(*) as count FROM atoms');
        atomCount = parseInt(atomResult.rows?.[0]?.count || '0', 10);
      } catch { /* table may not exist */ }

      try {
        const distillResult = await db.run('SELECT COUNT(*) as count FROM distills');
        distillCount = parseInt(distillResult.rows?.[0]?.count || '0', 10);
      } catch { /* table may not exist */ }

      // Dispatcher pool metrics (Phase 3)
      const dispatcher = (globalThis as any).__ANCHOR_DISPATCHER__;
      let pools: Record<string, string> | undefined;
      if (dispatcher?.getStats) {
        const ds = dispatcher.getStats();
        pools = {};
        for (const pool of ['poolA', 'poolB', 'poolC'] as const) {
          const s = ds[pool];
          if (!s) continue;
          pools[`p${pool.slice(-1).toLowerCase()}`] = `${s.healthStatus} workers=${s.activeWorkers || 0}/${s.maxThreads || s.maxConcurrent || '?'} completed=${s.totalCompleted || 0} failed=${s.totalFailed || 0}${s.cache ? ` cache=${s.cache.size}/${s.cache.capacity}` : ''}`;
        }
      }

      res.json({
        status: 'success',
        stats: {
          uptime_ms: uptimeMs,
          uptime_human: formatUptime(uptimeMs),
          memory: {
            heap_used_mb: Math.round(memUsage.heapUsed / 1024 / 1024),
            heap_total_mb: Math.round(memUsage.heapTotal / 1024 / 1024),
            rss_mb: Math.round(memUsage.rss / 1024 / 1024),
          },
          database: {
            molecules: moleculeCount,
            atoms: atomCount,
            distills: distillCount,
          },
          operations: {
            search_count: searchCount,
            ingest_count: ingestCount,
          },
          dispatcher_pools: pools,
          timestamp: new Date().toISOString(),
        },
      });
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });
}

function formatUptime(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  if (days > 0) return `${days}d ${hours % 24}h ${minutes % 60}m`;
  if (hours > 0) return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
  return `${seconds}s`;
}
