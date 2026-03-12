import { Application, Request, Response } from 'express';
import { z } from 'zod';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { AtomizerService } from '../../services/ingest/atomizer-service.js';
import { AtomicIngestService } from '../../services/ingest/ingest-atomic.js';
import { ingestSchema } from '../../schemas/api-schemas.js';

export function setupIngestRoutes(app: Application) {
  // Ingestion endpoint (Atomic Architecture)
  app.post('/v1/ingest', async (req: Request, res: Response) => {
    const startTime = Date.now();

    // Validate request body with Zod
    const validation = ingestSchema.safeParse(req.body);
    if (!validation.success) {
      StructuredLogger.warn('INGEST_VALIDATION_ERROR', { errors: validation.error.issues });
      return res.status(400).json({
        error: 'Invalid ingest request',
        details: validation.error.issues.map(e => ({
          field: e.path.join('.'),
          message: e.message
        }))
      });
    }

    try {
      const { content, source, type, bucket, buckets = [], tags = [] } = validation.data;

      if (!content) {
        StructuredLogger.warn('INGEST_INVALID_REQUEST', { error: 'Content is required' });
        res.status(400).json({ error: 'Content is required' });
        return;
      }

      StructuredLogger.info('INGEST_REQUEST', {
        source: source || 'api_upload',
        content_length: content.length,
        buckets: buckets.length > 0 ? buckets : [bucket || 'notebook']
      });

      // Use legacy Atomizer pipeline for performance
      const atomizer = new AtomizerService();
      const atomicIngest = new AtomicIngestService();

      const provenance = (source && (source.includes('external') || source.includes('web'))) ? 'external' : 'internal';

      const atomizeResult = await atomizer.atomize(
        content,
        source || 'api_upload',
        provenance
      );

      // Skip ingestion if transient data was detected
      if (!atomizeResult) {
        const result = {
          status: 'skipped',
          message: 'Content skipped (transient data detected)',
          id: null,
          duration_ms: Date.now() - startTime
        };
        return res.json(result);
      }

      const { compound, molecules, atoms } = atomizeResult;

      // Ingest result
      const targetBuckets = buckets.length > 0 ? buckets : [bucket || 'notebook'];
      await atomicIngest.ingestResult(compound, molecules, atoms, targetBuckets);

      const duration = Date.now() - startTime;

      StructuredLogger.ingestion('success', {
        source: source || 'api_upload',
        compound_id: compound.id,
        atoms_count: atoms.length,
        molecules_count: molecules.length,
        buckets: targetBuckets,
        duration_ms: duration
      });

      const result = {
        status: 'success',
        message: `Ingested ${atoms.length} atoms and ${molecules.length} molecules`,
        id: compound.id,
        duration_ms: duration
      };

      res.status(200).json(result);
    } catch (e: any) {
      const duration = Date.now() - startTime;
      StructuredLogger.error('INGEST_ERROR', e, {
        duration_ms: duration
      });
      res.status(500).json({ error: e.message });
    }
  });
}
