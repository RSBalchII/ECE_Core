import { Application, Request, Response } from 'express';
import { validate, schemas } from '../../middleware/validate.js';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { smartChatSearch, executeMoleculeSearch } from '../../services/search/search.js';
import { SearchRequest } from '../../types/api.js';

export function setupSearchRoutes(app: Application) {
  // POST Search endpoint (Standard UniversalRAG + Iterative Logic)
  // Supports strategy parameter: 'standard' (default) or 'max-recall'
  app.post('/v1/memory/search', validate(schemas.memorySearch), async (req: Request, res: Response) => {
    const startTime = Date.now();
    StructuredLogger.info('SEARCH_REQUEST', {
      endpoint: '/v1/memory/search',
      method: 'POST'
    });

    try {
      const body = req.body as SearchRequest;
      if (!body.query) {
        StructuredLogger.warn('SEARCH_INVALID_REQUEST', { error: 'Query is required' });
        res.status(400).json({ error: 'Query is required' });
        return;
      }

      const strategy = (req.body as any).strategy || 'standard';

      // Standard 113: Dual-Strategy Search (Automatic Max-Recall for large budgets)
      // Automatically switch to max-recall for queries over 16k tokens (65k chars)
      const tokenBudget = (req.body as any).token_budget || 0;
      const maxChars = body.max_chars || 100000;
      const estimatedTokens = maxChars / 4;

      let useMaxRecall = strategy === 'max-recall';
      if (!useMaxRecall && estimatedTokens > 16000) {
        useMaxRecall = true;
        StructuredLogger.info('SEARCH_AUTO_MAX_RECALL', {
          reason: 'token_budget > 16k',
          estimated_tokens: estimatedTokens,
          max_chars: maxChars
        });
      }

      StructuredLogger.info('SEARCH_PROCESSING', {
        query: body.query.substring(0, 100),
        query_length: body.query.length,
        strategy: useMaxRecall ? 'max-recall' : 'standard',
        estimated_tokens: estimatedTokens
      });

      // Handle legacy params
      const bucketParam = (req.body as any).bucket;
      const buckets = body.buckets || [];
      const allBuckets = bucketParam ? [...buckets, bucketParam] : buckets;
      // Use config limit (default 100k) if no budget provided
      const defaultLimit = 100000;
      const budget = (req.body as any).token_budget ? (req.body as any).token_budget * 4 : (body.max_chars || defaultLimit);
      const tags = (req.body as any).tags || [];

      // Enhanced Search Strategy (Standard 086)
      // Support both standard and max-recall strategies
      StructuredLogger.info('SEARCH_STRATEGY', { strategy: useMaxRecall ? 'max-recall' : 'standard' });

      let result;
      if (useMaxRecall) {
        // Max Recall Strategy: Zero temporal decay, 3 hops, no relevance filtering
        result = await smartChatSearch(
          body.query,
          allBuckets,
          budget,
          tags,
          (req.body as any).provenance || 'all',
          true,  // useMaxRecall = true
          body.user_context
        );
      } else {
        // Standard Strategy: Balanced 70/30 budget with temporal decay
        result = await smartChatSearch(
          body.query,
          allBuckets,
          budget,
          tags,
          (req.body as any).provenance || 'all',
          false,  // useMaxRecall = false
          body.user_context
        );
      }

      const duration = Date.now() - startTime;
      const resultCount = result.results.length;

      // Log search completion with metrics
      StructuredLogger.search(body.query, resultCount, duration, {
        strategy: strategy || 'enhanced_tag_walker',
        buckets: allBuckets,
        budget
      });

      StructuredLogger.info('SEARCH_RESPONSE', {
        query: body.query.substring(0, 50),
        results_count: resultCount,
        duration_ms: duration,
        strategy: strategy || 'enhanced_tag_walker'
      });

      // Construct standard response
      if (!res.headersSent) {
        res.status(200).json({
          status: 'success',
          context: result.context,
          results: result.results,
          strategy: strategy || 'enhanced_tag_walker',
          attempt: (result as any).attempt || 1,
          split_queries: result.splitQueries || [],
          metadata: {
            engram_hits: 0,
            vector_latency: 0,
            provenance_boost_active: true,
            search_type: strategy === 'max-recall' ? 'max_recall' : 'enhanced',
            temporal_decay: strategy === 'max-recall' ? 0.0 : 0.00001,
            max_hops: strategy === 'max-recall' ? 3 : 1,
            damping: strategy === 'max-recall' ? 1.0 : 0.85,
            min_relevance: strategy === 'max-recall' ? 0.0 : 0.1,
            ...((result as any).metadata || {})
          }
        });
      }
    } catch (error: any) {
      const duration = Date.now() - startTime;
      StructuredLogger.error('SEARCH_ERROR', error, {
        duration_ms: duration
      });

      // Check if headers have already been sent to avoid duplicate responses
      if (!res.headersSent) {
        res.status(500).json({
          error: 'Internal server error during search',
          details: error.message
        });
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
      // Default to 256K chars for max recall
      const budget = body.token_budget ? body.token_budget * 4 : (body.max_chars || 262144);
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
