import type { Application, Request, Response } from 'express';
import rateLimit from 'express-rate-limit';
import { validate, schemas } from '../../middleware/validate.js';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { AtomizerService } from '../../services/ingest/atomizer-service.js';
import { AtomicIngestService } from '../../services/ingest/ingest-atomic.js';
import { writeContentToMirror } from '../../services/mirror/write-content-to-mirror.js';
import { writeMirroredFile } from '../../services/mirror/mirror.js';

// Counter for ingest requests
let ingestCounter = 0;

// Rate limiter for ingest endpoints
// Mobile-friendly defaults: 10 requests per minute for ingest, 30 for general API
const ingestLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 10, // 10 requests per minute
  message: {
    error: 'Too many ingest requests',
    retryAfter: 60, // seconds
  },
  standardHeaders: true, // Return rate limit info in `RateLimit-*` headers
  legacyHeaders: false, // Disable `X-RateLimit-*` headers
  keyGenerator: (req: Request) => {
    // Rate limit by IP address
    return req.ip || req.socket.remoteAddress || 'unknown';
  },
  // Skip rate limiting for local development
  skip: (req: Request) => {
    const isLocalhost = req.ip === '127.0.0.1' || req.ip === '::1' || req.ip?.startsWith('192.168.');
    if (isLocalhost && process.env.NODE_ENV === 'development') {
      return true;
    }
    return false;
  },
});

// General API limiter (less restrictive)
const apiLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 100, // 100 requests per minute
  message: {
    error: 'Too many API requests',
    retryAfter: 60, // seconds
  },
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req: Request) => req.ip || req.socket.remoteAddress || 'unknown',
});

export function setupIngestRoutes(app: Application) {
  // Apply rate limiting to all ingest routes
  app.use('/v1/ingest', ingestLimiter);

  // Ingestion endpoint (Atomic Architecture)
  app.post('/v1/ingest', validate(schemas.ingest), async (req: Request, res: Response) => {
    // Increment ingest counter
    ingestCounter++;
    const startTime = Date.now();
    try {
      const { content, source, type, bucket, buckets = [], tags = [] } = req.body;

      if (!content) {
        StructuredLogger.warn('INGEST_INVALID_REQUEST', { error: 'Content is required' });
        res.status(400).json({ error: 'Content is required' });
        return;
      }

      StructuredLogger.info('INGEST_REQUEST', {
        source: source || 'api_upload',
        content_length: content.length,
        buckets: buckets.length > 0 ? buckets : [bucket || 'notebook'],
      });

      // Use legacy Atomizer pipeline for performance
      const atomizer = new AtomizerService();
      const atomicIngest = new AtomicIngestService();

      const provenance = (source && (source.includes('external') || source.includes('web'))) ? 'external' : 'internal';

      const atomizeResult = await atomizer.atomize(
        content,
        source || 'api_upload',
        provenance,
      );

      // Skip ingestion if transient data was detected
      if (!atomizeResult) {
        const result = {
          status: 'skipped',
          message: 'Content skipped (transient data detected)',
          id: null,
          duration_ms: Date.now() - startTime,
        };
        return res.json(result);
      }

      const { compound, molecules, atoms } = atomizeResult;

      // Ingest result - store compound in database first
      const targetBuckets = buckets.length > 0 ? buckets : [bucket || 'notebook'];

      await atomicIngest.ingestResult(compound, molecules, atoms, targetBuckets);

      // Write content to mirror after successful DB storage (Pointer-Only Architecture)
      if (compound.path && content) {
        try {
          // Generate a proper relative path for the mirror (not absolute-style @inbox/...)
          const ext = '.md'; // Default extension for text uploads
          const safeId = (compound.id || '').replace(/[^a-zA-Z0-9]/g, '-');
          const mirrorPath = `inbox/${Date.now()}_${safeId}.${ext}`;

          // Write raw content to mirrored brain filesystem using writeContentToMirror helper
          await writeContentToMirror(mirrorPath, content);

          // Update compound path to point to the mirror location
          compound.path = mirrorPath;

          StructuredLogger.info('MIRROR_WRITE', {
            path: mirrorPath,
            content_length: content.length,
            provenance: compound.provenance || 'internal',
          });
        } catch (mirrorError) {
          // Log but don't fail ingestion if mirror write fails
          const error = mirrorError as Error;
          StructuredLogger.warn('MIRROR_WRITE_FAILED', {
            path: compound.path,
            error: error.message,
          });
        }
      }

      const duration = Date.now() - startTime;

      StructuredLogger.ingestion('success', {
        source: source || 'api_upload',
        compound_id: compound.id,
        atoms_count: atoms.length,
        molecules_count: molecules.length,
        buckets: targetBuckets,
        duration_ms: duration,
      });

      const result = {
        status: 'success',
        message: `Ingested ${atoms.length} atoms and ${molecules.length} molecules`,
        id: compound.id,
        duration_ms: duration,
      };

      res.status(200).json(result);
    } catch (e: any) {
      const duration = Date.now() - startTime;
      StructuredLogger.error('INGEST_ERROR', e, {
        duration_ms: duration,
      });
      res.status(500).json({ error: e.message });
    }
  });
}
