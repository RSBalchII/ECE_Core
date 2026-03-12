import { Application, Request, Response } from 'express';
import { z } from 'zod';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { smartChatSearch, executeMoleculeSearch } from '../../services/search/search.js';
import { executeStreamingSearch, formatSSE } from '../../services/search/streaming-search.js';
import { searchSchema, moleculeSearchSchema, maxRecallSearchSchema } from '../../schemas/api-schemas.js';

export function setupSearchRoutes(app: Application) {
  // POST Search endpoint (Standard 136: Streaming Search)
  // Memory-efficient streaming search with Server-Sent Events
  app.post('/v1/memory/search', async (req: Request, res: Response) => {
    const startTime = Date.now();

    // Validate request body with Zod
    const validation = searchSchema.safeParse(req.body);
    if (!validation.success) {
      StructuredLogger.warn('SEARCH_VALIDATION_ERROR', { errors: validation.error.issues });
      return res.status(400).json({
        error: 'Invalid search request',
        details: validation.error.issues.map(e => ({
          field: e.path.join('.'),
          message: e.message
        }))
      });
    }

    try {
      const body = validation.data;
      if (!body.query) {
        res.status(400).json({ error: 'Query is required' });
        return;
      }

      const strategy = (req.body as any).strategy || 'standard';
      const maxChars = body.max_chars || 5000;
      const estimatedTokens = maxChars / 4;
      const batchSize = (req.body as any).batch_size || 20;

      // Auto-switch to max-recall for large budgets
      let useMaxRecall = strategy === 'max-recall';
      if (!useMaxRecall && estimatedTokens > 16000) {
        useMaxRecall = true;
      }

      StructuredLogger.info('STREAMING_SEARCH_REQUEST', {
        query: body.query.substring(0, 100),
        strategy: useMaxRecall ? 'max-recall' : 'standard',
        batchSize
      });

      // Set up SSE headers
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      res.setHeader('X-Accel-Buffering', 'no');

      // Handle legacy params
      const bucketParam = (req.body as any).bucket;
      const buckets = body.buckets || [];
      const allBuckets = bucketParam ? [...buckets, bucketParam] : buckets;
      const tags = (req.body as any).tags || [];

      // Execute streaming search
      const stream = executeStreamingSearch({
        query: body.query,
        buckets: allBuckets,
        maxChars,
        tags,
        provenance: (req.body as any).provenance || 'all',
        useMaxRecall,
        userContext: body.user_context,
        batchSize
      });

      // Stream results to client
      for await (const event of stream) {
        res.write(formatSSE(event));

        if (event.type === 'error') {
          res.end();
          return;
        }
      }

      // Send final completion event
      const duration = Date.now() - startTime;
      res.write(formatSSE({
        type: 'metadata',
        strategy: useMaxRecall ? 'max-recall' : 'standard',
        totalResults: 0,
        query: body.query,
        durationMs: duration
      }));

      res.end();

      StructuredLogger.info('STREAMING_SEARCH_COMPLETE', {
        query: body.query.substring(0, 100),
        durationMs: duration
      });

    } catch (error: any) {
      const duration = Date.now() - startTime;
      StructuredLogger.error('STREAMING_SEARCH_ERROR', error, {
        durationMs: duration
      });

      if (!res.headersSent) {
        res.status(500).json({
          error: 'Internal server error during streaming search',
          details: error.message
        });
      } else {
        res.write(formatSSE({
          type: 'error',
          message: error.message,
          details: error.stack
        }));
        res.end();
      }
    }
  });

  // GET Search (Legacy support) - redirect to use POST effectively
  app.get('/v1/memory/search', async (_req: Request, res: Response) => {
    res.status(400).json({ error: "Use POST /v1/memory/search for complex queries." });
  });

  // POST Molecule Search endpoint - splits query into sentence-like chunks
  app.post('/v1/memory/molecule-search', async (req: Request, res: Response) => {
    try {
      const body = req.body;
      if (!body.query) {
        res.status(400).json({ error: 'Query is required' });
        return;
      }

      // Handle legacy params
      const bucketParam = body.bucket;
      const buckets = body.buckets || [];
      const allBuckets = bucketParam ? [...buckets, bucketParam] : buckets;
      const budget = body.token_budget ? body.token_budget * 4 : (body.max_chars || 2400); // Default to 2400 as specified
      const tags = body.tags || [];

      // Use Molecule Search Strategy - split query into sentence-like chunks
      const result = await executeMoleculeSearch(
        body.query,
        undefined, // bucket
        allBuckets,
        budget,
        false, // deep
        'all', // provenance
        tags,
        body.user_context
      );

      // Construct standard response
      console.log(`[API] Molecule Search "${body.query}" -> Found ${result.results.length} results`);

      res.status(200).json({
        status: 'success',
        context: result.context,
        results: result.results,
        strategy: 'molecule_split',
        metadata: {
          engram_hits: 0,
          vector_latency: 0,
          provenance_boost_active: true,
          ...(result.metadata || {})
        }
      });
    } catch (error: any) {
      console.error('Molecule Search error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // POST Maximum Recall Search - uses MAX_RECALL_CONFIG for comprehensive retrieval
  app.post('/v1/memory/search-max-recall', async (req: Request, res: Response) => {
    try {
      const body = req.body;
      if (!body.query) {
        res.status(400).json({ error: 'Query is required' });
        return;
      }

      // Handle legacy params
      const bucketParam = body.bucket;
      const buckets = body.buckets || [];
      const allBuckets = bucketParam ? [...buckets, bucketParam] : buckets;
      // Default to 16K chars for max recall (mobile-friendly)
      const budget = body.token_budget ? body.token_budget * 4 : (body.max_chars || 16384);
      const tags = body.tags || [];

      // Use max-recall configuration
      const result = await smartChatSearch(
        body.query,
        allBuckets,
        budget,
        tags,
        'all', // provenance
        true,   // useMaxRecall = true
        body.user_context
      );

      console.log(`[API] Max Recall Search "${body.query}" -> Found ${result.results.length} results`);

      res.status(200).json({
        status: 'success',
        context: result.context,
        results: result.results,
        strategy: 'max_recall',
        split_queries: result.splitQueries,
        metadata: {
          ...result.metadata,
          max_recall_enabled: true,
          temporal_decay: 0.0,
          max_hops: 3,
          damping: 1.0,
          min_relevance: 0.0
        }
      });
    } catch (error: any) {
      console.error('Max Recall Search error:', error);
      res.status(500).json({ error: error.message });
    }
  });
}
