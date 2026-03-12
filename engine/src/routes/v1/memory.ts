/**
 * Memory routes — explore / illuminate endpoint
 *
 * POST /v1/memory/explore
 *   BFS graph traversal from seed concepts.
 *   Returns the connected subgraph as structural corpus compression.
 *
 * POST /v1/memory/distill
 *   Standard 133: Radial Distillation
 *   Line-level deduplication with radial inflation.
 */

import { Application, Request, Response } from 'express';
import { z } from 'zod';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { exploreMemory, ExploreRequest } from '../../services/search/explore.js';
import { radialDistill, RadialDistillRequest } from '../../services/distillation/radial-distiller.js';
import { exploreSchema, distillSchema } from '../../schemas/api-schemas.js';

export function setupMemoryRoutes(app: Application) {
  app.post('/v1/memory/explore', async (req: Request, res: Response) => {
    const startTime = Date.now();

    // Validate request body with Zod
    const validation = exploreSchema.safeParse(req.body);
    if (!validation.success) {
      StructuredLogger.warn('EXPLORE_VALIDATION_ERROR', { errors: validation.error.issues });
      return res.status(400).json({
        error: 'Invalid explore request',
        details: validation.error.issues.map(e => ({
          field: e.path.join('.'),
          message: e.message
        }))
      });
    }

    StructuredLogger.info('EXPLORE_REQUEST', { endpoint: '/v1/memory/explore' });

    try {
      const body = validation.data as ExploreRequest;

      if (!body?.seed || (!body.seed.global && !body.seed.query && !body.seed.atom_ids?.length)) {
        res.status(400).json({ error: 'seed.query, seed.atom_ids, or seed.global:true is required' });
        return;
      }

      const result = await exploreMemory(body);
      const duration = Date.now() - startTime;

      StructuredLogger.info('EXPLORE_COMPLETE', {
        nodes: result.stats.nodes_count,
        strategy: result.stats.strategy,
        duration_ms: duration
      });

      // Normalise to a consistent shape regardless of flat/graph format
      if (result.nodes !== undefined && !('results' in result)) {
        // graph or flat — return as-is but also expose `results` alias for MCP compatibility
        res.json({
          ...result,
          results: result.nodes.map(n => ({
            id: n.id,
            content: n.content,
            source: n.source,
            tags: n.tags,
            score: 1
          })),
          duration_ms: duration
        });
      } else {
        res.json({ ...result, duration_ms: duration });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      StructuredLogger.error('EXPLORE_ERROR', err instanceof Error ? err : new Error(msg), { error: msg });
      res.status(500).json({ error: msg });
    }
  });

  app.post('/v1/memory/distill', async (req: Request, res: Response) => {
    const startTime = Date.now();

    // Validate request body with Zod
    const validation = distillSchema.safeParse(req.body);
    if (!validation.success) {
      StructuredLogger.warn('DISTILL_VALIDATION_ERROR', { errors: validation.error.issues });
      return res.status(400).json({
        error: 'Invalid distill request',
        details: validation.error.issues.map(e => ({
          field: e.path.join('.'),
          message: e.message
        }))
      });
    }

    StructuredLogger.info('DISTILL_REQUEST', {
      endpoint: '/v1/memory/distill',
      mode: 'radial'
    });

    try {
      // Standard 133: Radial Distillation (only mode supported)
      const body = validation.data as RadialDistillRequest;
      const result = await radialDistill(body);
      const duration = Date.now() - startTime;

      StructuredLogger.info('RADIAL_DISTILL_COMPLETE', {
        compounds_processed: result.stats.compounds_processed,
        lines_total: result.stats.lines_total,
        lines_unique: result.stats.lines_unique,
        compression_ratio: result.stats.compression_ratio,
        duration_ms: duration
      });

      res.json({
        ...result,
        duration_ms: duration
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      StructuredLogger.error('DISTILL_ERROR', err instanceof Error ? err : new Error(msg), { error: msg });
      res.status(500).json({ error: msg });
    }
  });
}
