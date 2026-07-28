/**
 * Distill Routes - Version Control for Distills (Standard 016)
 *
 * API endpoints for managing and querying distill checkpoints.
 */

import type { Application, Request, Response } from 'express';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { getAllDistills, getDistill, getDistillsBySession, deleteDistill } from '../../services/distillation/distill-manager.js';
import { radialDistill } from '../../services/distillation/radial-distiller-v2.js';

export function setupDistillRoutes(app: Application) {
  // GET /v1/distills/list - List all distills (newest first)
  app.get('/v1/distills/list', async (req: Request, res: Response) => {
    try {
      const limit = parseInt(req.query.limit as string) || 50;
      const distills = await getAllDistills(limit);

      StructuredLogger.info('DISTILLS_LIST', { count: distills.length });

      res.json({
        status: 'success',
        distills,
        count: distills.length,
        timestamp: new Date().toISOString(),
      });
    } catch (error: any) {
      StructuredLogger.error('DISTILLS_LIST_ERROR', error);
      res.status(500).json({ error: error.message });
    }
  });

  // GET /v1/distills/:id - Get a specific distill by ID
  app.get('/v1/distills/:id', async (req: Request, res: Response) => {
    const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
    try {
      const distill = await getDistill(id);

      if (!distill) {
        res.status(404).json({ error: 'Distill not found' });
        return;
      }

      StructuredLogger.info('DISTILL_GET', { id: id });

      res.json({
        status: 'success',
        distill,
        timestamp: new Date().toISOString(),
      });
    } catch (error: any) {
      StructuredLogger.error('DISTILL_GET_ERROR', error, { id: id });
      res.status(500).json({ error: error.message });
    }
  });

  // GET /v1/distills/session/:sessionId - Get distills for a session
  app.get('/v1/distills/session/:sessionId', async (req: Request, res: Response) => {
    const sessionId = Array.isArray(req.params.sessionId) ? req.params.sessionId[0] : req.params.sessionId;
    try {
      const distills = await getDistillsBySession(sessionId);

      StructuredLogger.info('DISTILLS_BY_SESSION', {
        sessionId: sessionId,
        count: distills.length,
      });

      res.json({
        status: 'success',
        sessionId: sessionId,
        distills,
        count: distills.length,
        timestamp: new Date().toISOString(),
      });
    } catch (error: any) {
      StructuredLogger.error('DISTILLS_BY_SESSION_ERROR', error, { sessionId: sessionId });
      res.status(500).json({ error: error.message });
    }
  });

  // DELETE /v1/distills/:id - Delete a distill (file must be deleted separately)
  app.delete('/v1/distills/:id', async (req: Request, res: Response) => {
    const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
    try {
      const deleted = await deleteDistill(id);

      if (!deleted) {
        res.status(404).json({ error: 'Distill not found' });
        return;
      }

      StructuredLogger.info('DISTILL_DELETED', { id: id });

      res.json({
        status: 'success',
        message: 'Distill deleted from database',
        id: id,
        timestamp: new Date().toISOString(),
      });
    } catch (error: any) {
      StructuredLogger.error('DISTILL_DELETE_ERROR', error, { id: id });
      res.status(500).json({ error: error.message });
    }
  });

  // POST /v1/distills/trigger - Manually trigger radial distillation
  app.post('/v1/distills/trigger', async (req: Request, res: Response) => {
    try {
      const {
        seed_query,
        seed_ids,
        radius = 2000,
        output_format = 'decision-records',
        output_path,
        export_to_inbox = false,
      } = req.body as any;

      StructuredLogger.info('DISTILL_TRIGGER', {
        seed_query: seed_query || seed_ids || 'all',
        radius,
        output_format,
      });

      const radialRequest = {
        seed: seed_ids ? { compound_ids: seed_ids } : { query: seed_query },
        radius,
        max_radius: radius * 2,
        output_format,
        output_path,
        export_to_inbox,
      };

      const result = await radialDistill(radialRequest);

      res.status(200).json({
        status: 'success',
        message: 'Distillation complete',
        result: {
          compounds_processed: result.stats.compounds_processed,
          blocks_total: result.stats.blocks_total,
          blocks_unique: result.stats.blocks_unique,
          compression_ratio: result.stats.compression_ratio,
          duration_ms: result.stats.duration_ms,
          memory_peak_mb: result.stats.memory_peak_mb,
          output: result.output,
        },
        timestamp: new Date().toISOString(),
      });
    } catch (error: any) {
      StructuredLogger.error('DISTILL_TRIGGER_ERROR', error);
      res.status(500).json({
        error: 'Distillation failed',
        message: error.message,
        timestamp: new Date().toISOString(),
      });
    }
  });
}
