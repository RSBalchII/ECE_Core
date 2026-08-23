import type { Application, Request, Response } from 'express';
import { validate, schemas } from '../../middleware/validate.js';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { smartChatSearch, executeMoleculeSearch } from '../../services/search/search.js';
import { safeTimestamp } from '../../services/search/search-utils.js';
import type { SearchRequest } from '../../types/api.js';
import { executeStreamingSearch, formatSSE } from '../../services/search/streaming-search.js';

// Counter for search requests
let searchCounter = 0;

export function setupSearchRoutes(app: Application) {
  // POST Search endpoint (Standard 136: Streaming Search)
  // Memory-efficient streaming search with Server-Sent Events
  // Supports both streaming (default) and non-streaming modes via query param
  app.post('/v1/memory/search', validate(schemas.memorySearch), async (req: Request, res: Response) => {
    // Increment search counter
    searchCounter++;
    const startTime = Date.now();

    try {
      const body = req.body as SearchRequest;
      if (!body.query || body.query.trim() === '') {
        res.status(400).json({ error: 'Query is required and cannot be empty or whitespace-only' });
        return;
      }

      // Check for non-streaming mode (FRICTIONLESS_SPEC.md section 4.3)
      const streamMode = req.query.stream !== 'false';
      
      const strategy = (req.body).strategy || 'standard';
      const maxChars = body.max_chars || 5000;
      const estimatedTokens = maxChars / 4;
      const batchSize = (req.body).batch_size || 20;

      // Auto-switch to max-recall for large budgets
      let useMaxRecall = strategy === 'max-recall';
      if (!useMaxRecall && estimatedTokens > 16000) {
        useMaxRecall = true;
      }

      StructuredLogger.info('STREAMING_SEARCH_REQUEST', {
        query: body.query.substring(0, 100),
        strategy: useMaxRecall ? 'max-recall' : 'standard',
        batchSize,
        streamMode,
      });

      // Handle legacy params
      const bucketParam = (req.body).bucket;
      const buckets = body.buckets || [];
      const allBuckets = bucketParam ? [...buckets, bucketParam] : buckets;
      const tags = (req.body).tags || [];

      if (!streamMode) {
        // Non-streaming mode: Return single JSON response with content (FRICTIONLESS_SPEC.md section 4.1)
        const searchResult = await smartChatSearch(
          body.query,
          allBuckets,
          maxChars,
          tags,
          (req.body).provenance || 'all',
          useMaxRecall,
          body.user_context,
        );

        const duration = Date.now() - startTime;

        // Format results with content (FRICTIONLESS_SPEC.md section 4.1)
        const formattedResults = searchResult.results.map(r => ({
          uuid: r.id,
          content: r.content,
          source: r.source,
          timestamp: safeTimestamp(r.timestamp),
          score: r.score,
          tags: r.tags || [],
          buckets: r.buckets || [],
          provenance: r.provenance,
          compound_id: r.compound_id,
          start_byte: r.start_byte,
          end_byte: r.end_byte,
        }));

        const response: any = {
          metadata: {
            totalResults: formattedResults.length,
            durationMs: duration,
            strategy: searchResult.strategy,
          },
          results: formattedResults,
        };

        // Add debug info if requested (FRICTIONLESS_SPEC.md section 4.2)
        if (req.query.debug === 'true') {
          response.debug = {
            queryTags: tags,
            bucketsSearched: allBuckets,
            useMaxRecall,
            charBudget: maxChars,
            splitQueries: searchResult.splitQueries || [],
            metadataFromSearch: searchResult.metadata || {},
          };
        }

        StructuredLogger.info('NON_STREAMING_SEARCH_COMPLETE', {
          query: body.query.substring(0, 100),
          totalResults: formattedResults.length,
          durationMs: duration,
        });

        res.status(200).json(response);
        return;
      }

      // Streaming mode: Execute streaming search
      const stream = executeStreamingSearch({
        query: body.query,
        buckets: allBuckets,
        maxChars,
        tags,
        provenance: (req.body).provenance || 'all',
        useMaxRecall,
        userContext: body.user_context,
        batchSize,
      });

      // Set up SSE headers
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      res.setHeader('X-Accel-Buffering', 'no');

      // Stream results to client with progress tracking
      let totalResults = 0;
      for await (const event of stream) {
        res.write(formatSSE(event));

        // Accumulate result count from batch events
        if (event.type === 'batch') {
          totalResults += event.results.length;
        }
        
        // Also track from progress events for accurate cumulative count
        if (event.type === 'progress' && event.currentResults !== undefined) {
          totalResults = Math.max(totalResults, event.currentResults);
        }

        if (event.type === 'error') {
          res.end();
          return;
        }
      }

      // Send final completion event with actual result count
      const duration = Date.now() - startTime;
      res.write(formatSSE({
        type: 'metadata',
        strategy: useMaxRecall ? 'max-recall' : 'standard',
        totalResults,
        query: body.query,
        durationMs: duration,
      }));

      res.end();

      StructuredLogger.info('STREAMING_SEARCH_COMPLETE', {
        query: body.query.substring(0, 100),
        durationMs: duration,
      });

    } catch (error: any) {
      const duration = Date.now() - startTime;
      StructuredLogger.error('STREAMING_SEARCH_ERROR', error, {
        durationMs: duration,
      });

      if (!res.headersSent) {
        res.status(500).json({
          error: 'Internal server error during streaming search',
          details: error.message,
        });
      } else {
        res.write(formatSSE({
          type: 'error',
          message: error.message,
          details: error.stack,
        }));
        res.end();
      }
    }
  });

  // GET Search (Legacy support) - redirect to use POST effectively
  app.get('/v1/memory/search', async (_req: Request, res: Response) => {
    res.status(400).json({ error: 'Use POST /v1/memory/search for complex queries.' });
  });

  // POST Molecule Search endpoint - splits query into sentence-like chunks
  app.post('/v1/memory/molecule-search', async (req: Request, res: Response) => {
    try {
      const { body } = req;
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
        tags,
        body.user_context,
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
          ...(result.metadata || {}),
        },
      });
    } catch (error: any) {
      console.error('Molecule Search error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // POST Maximum Recall Search - uses MAX_RECALL_CONFIG for comprehensive retrieval
  app.post('/v1/memory/search-max-recall', async (req: Request, res: Response) => {
    try {
      const { body } = req;
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
        body.user_context,
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
          min_relevance: 0.0,
        },
      });
    } catch (error: any) {
      console.error('Max Recall Search error:', error);
      res.status(500).json({ error: error.message });
    }
  });
}
