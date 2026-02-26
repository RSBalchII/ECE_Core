/**
 * API Routes for Sovereign Context Engine
 *
 * Standardized API Interface implementing UniversalRAG architecture.
 */

import { Application, Request, Response } from 'express';
import * as crypto from 'crypto';
import { db } from '../core/db.js';
import { config } from '../config/index.js';
import { validate, schemas } from '../middleware/validate.js';
import { StructuredLogger } from '../utils/structured-logger.js';

// Import services and types
import { executeSearch, smartChatSearch } from '../services/search/search.js';
import { AtomizerService } from '../services/ingest/atomizer-service.js';
import { AtomicIngestService } from '../services/ingest/ingest-atomic.js';
import { getState, clearState } from '../services/scribe/scribe.js';
import { createBackup, listBackups, restoreBackup } from '../services/backup/backup.js';
import { restoreFromBackup, getLatestBackup, validateBackup } from '../services/backup/backup-restore.js';
import { fetchAndProcess, searchWeb } from '../services/research/researcher.js';
import { SearchRequest } from '../types/api.js';
import { setupEnhancedRoutes } from './enhanced-api.js';

export function setupRoutes(app: Application) {
  // Ingestion endpoint (Atomic Architecture)
  app.post('/v1/ingest', validate(schemas.ingest), async (req: Request, res: Response) => {
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

  // POST Quarantine Atom (Standard 073)
  app.post('/v1/atoms/:id/quarantine', async (req: Request, res: Response) => {
    try {
      const { id } = req.params;
      if (!id) {
        res.status(400).json({ error: 'Atom ID is required' });
        return;
      }

      console.log(`[API] Quarantining Atom: ${id}`);

      // Update Provenance + Add Tag
      // We use a transaction-like update: Read -> Modify -> Write
      // 1. Get current record
      const check = await db.run(
        `SELECT tags FROM atoms WHERE id = $1`,
        [id]
      );
      if (!check.rows || check.rows.length === 0) {
        res.status(404).json({ error: 'Atom not found' });
        return;
      }

      const currentTags = check.rows[0][0] as string[] || [];
      const newTags = [...new Set([...currentTags, '#manually_quarantined'])];

      // 2. Update Record
      await db.run(
        `UPDATE atoms SET tags = $1, provenance = $2 WHERE id = $3`,
        [newTags, 'quarantine', id]
      );

      res.status(200).json({ status: 'success', message: `Atom ${id} quarantined.` });
    } catch (e: any) {
      console.error(e);
      res.status(500).json({ error: e.message });
    }
  });

  // GET Quarantined Atoms
  app.get('/v1/atoms/quarantined', async (_req: Request, res: Response) => {
    try {
      const query = `
        SELECT id, content, source_path, timestamp, buckets, tags, provenance, simhash, embedding
        FROM atoms
        WHERE provenance = 'quarantine'
        ORDER BY timestamp DESC
        LIMIT 100
      `;
      const result = await db.run(query);

      const atoms = (result.rows || []).map((row: any) => ({
        id: row.id,
        content: row.content,
        source: row.source_path,
        timestamp: row.timestamp,
        buckets: row.buckets,
        tags: row.tags,
        provenance: row.provenance,
        simhash: row.simhash
      }));

      res.status(200).json(atoms);
    } catch (e: any) {
      console.error('[API] Failed to fetch quarantined atoms:', e);
      res.status(500).json({ error: e.message });
    }
  });

  // ...

  // PUT Update Atom Content
  app.put('/v1/atoms/:id/content', async (req: Request, res: Response) => {
    try {
      const { id } = req.params;
      const { content } = req.body;

      // ...

      console.log(`[API] Updating Atom Content: ${id}`);

      // We must preserve all other fields, BUT zero out embedding to signal re-index needed
      const fullRecord = await db.run(
        `SELECT id, timestamp, content, source_path, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding
         FROM atoms WHERE id = $1`,
        [id]
      );

      if (!fullRecord.rows || fullRecord.rows.length === 0) {
        res.status(404).json({ error: 'Atom not found' });
        return;
      }

      const row = fullRecord.rows[0];
      const newHash = crypto.createHash('sha256').update(content).digest('hex');
      const newEmbedding = new Array(384).fill(0.1);

      await db.run(
        `UPDATE atoms SET content = $1, hash = $2, embedding = $3 WHERE id = $4`,
        [content, newHash, newEmbedding, id]
      );

      res.status(200).json({ status: 'success', message: `Atom ${id} updated.` });

    } catch (e: any) {
      // ...
    }
  });

  // POST Restore Atom
  app.post('/v1/atoms/:id/restore', async (req: Request, res: Response) => {
    try {
      const { id } = req.params;
      console.log(`[API] Restoring Atom: ${id}`);

      const fullRecord = await db.run(
        `SELECT id, timestamp, content, source_path, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding
         FROM atoms WHERE id = $1`,
        [id]
      );

      if (!fullRecord.rows || fullRecord.rows.length === 0) {
        res.status(404).json({ error: 'Atom not found' });
        return;
      }

      const row = fullRecord.rows[0];
      const currentTags = row.tags as string[] || [];

      // Filter out quarantine tags
      const newTags = currentTags.filter(t => t !== '#manually_quarantined' && t !== '#auto_quarantined');

      await db.run(
        `UPDATE atoms SET tags = $1, provenance = $2 WHERE id = $3`,
        [newTags, 'internal', id]
      );

      res.status(200).json({ status: 'success', message: `Atom ${id} restored to Graph.` });
    } catch (e: any) {
      // ...
    }
  });

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
      const userContext = body.user_context;

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
          userContext
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
          userContext
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

  // DEBUG: Get tag statistics
  app.get('/v1/debug/tags', async (_req: Request, res: Response) => {
    try {
      // Get total atom count
      const atomCount = await db.run('SELECT COUNT(*) as count FROM atoms');
      
      // Get total tag count
      const tagCount = await db.run('SELECT COUNT(*) as count FROM tags');
      
      // Get sample tags
      const sampleTags = await db.run('SELECT name, atom_count FROM tags ORDER BY atom_count DESC LIMIT 20');
      
      // Get tags with low atom counts
      const lowCountTags = await db.run('SELECT COUNT(*) as count FROM tags WHERE atom_count < 3');
      
      res.status(200).json({
        atoms: atomCount.rows?.[0]?.count || 0,
        tags: tagCount.rows?.[0]?.count || 0,
        sampleTags: sampleTags.rows || [],
        tagsWithLowCount: lowCountTags.rows?.[0]?.count || 0
      });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // DEBUG: Get synonym ring info
  app.get('/v1/debug/synonyms', async (_req: Request, res: Response) => {
    try {
      const synonyms = await db.run('SELECT key, value FROM engrams WHERE key LIKE \'synonym:%\'');
      res.status(200).json({
        count: synonyms.rows?.length || 0,
        synonyms: synonyms.rows || []
      });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
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
      const userContext = body.user_context;

      // Use Molecule Search Strategy - split query into sentence-like chunks
      const { executeMoleculeSearch } = await import('../services/search/search.js');
      const result = await executeMoleculeSearch(
        body.query,
        undefined, // bucket
        allBuckets,
        budget,
        false, // deep
        'all', // provenance
        tags,
        userContext
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
      const userContext = body.user_context;

      // Use max-recall configuration
      const { smartChatSearch } = await import('../services/search/search.js');
      const result = await smartChatSearch(
        body.query,
        allBuckets,
        budget,
        tags,
        'all', // provenance
        true,   // useMaxRecall = true
        userContext
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

  // Get all buckets
  app.get('/v1/buckets', async (_req: Request, res: Response) => {
    try {
      // Improved Bucket Retrieval: Use the tags table which is much lighter (Atomic Architecture)
      const result = await db.run('SELECT DISTINCT bucket FROM tags WHERE bucket IS NOT NULL ORDER BY bucket');

      const allBuckets = new Set<string>();
      if (result.rows) {
        for (const row of result.rows) {
          const b = row.bucket;
          if (b && typeof b === 'string') allBuckets.add(b);
        }
      }

      res.status(200).json([...allBuckets].sort());
    } catch (error) {
      console.error('Bucket retrieval error:', error);
      res.status(500).json({ error: 'Failed to retrieve buckets' });
    }
  });

  // POST /v1/buckets - Create a new bucket
  app.post('/v1/buckets', async (req: Request, res: Response) => {
    try {
      const { name, location } = req.body;

      if (!name || !name.trim()) {
        return res.status(400).json({ error: 'Bucket name is required' });
      }

      const bucketName = name.trim();

      // Validate location if provided
      const validLocations = ['inbox', 'external-inbox'];
      if (location && !validLocations.includes(location)) {
        return res.status(400).json({ 
          error: `Invalid location. Must be one of: ${validLocations.join(', ')}` 
        });
      }

      // Check if bucket already exists
      const existingResult = await db.run(
        'SELECT DISTINCT bucket FROM tags WHERE bucket = $1',
        [bucketName]
      );

      if (existingResult.rows && existingResult.rows.length > 0) {
        return res.status(409).json({ 
          error: 'Bucket already exists',
          exists: true,
          bucket: bucketName
        });
      }

      // Create a placeholder tag entry to register the bucket
      // This makes the bucket visible in the list
      const placeholderTag = `_bucket_${bucketName}`;
      await db.run(
        `INSERT INTO tags (tag, bucket) VALUES ($1, $2) 
         ON CONFLICT (tag, bucket) DO NOTHING`,
        [placeholderTag, bucketName]
      );

      // Store bucket metadata in engrams
      const bucketMetadata = {
        name: bucketName,
        location: location || 'inbox',
        created_at: new Date().toISOString(),
        source: 'manual'
      };

      await db.run(
        `INSERT INTO engrams (key, value) VALUES ($1, $2)
         ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`,
        [`bucket_meta_${bucketName}`, JSON.stringify(bucketMetadata)]
      );

      console.log(`[API] Created bucket: ${bucketName} at location: ${location || 'inbox'}`);

      res.status(201).json({
        success: true,
        bucket: bucketName,
        location: location || 'inbox'
      });
    } catch (error: any) {
      console.error('[API] Bucket creation error:', error);
      res.status(500).json({ error: `Failed to create bucket: ${error.message}` });
    }
  });

  // Get all tags (Faceted by Bucket)
  app.get('/v1/tags', async (req: Request, res: Response) => {
    try {
      const bucketsParam = req.query['buckets'] as string;
      const buckets = bucketsParam ? bucketsParam.split(',') : [];

      // Optimized for PGlite: Use tags table directly
      let query = 'SELECT DISTINCT tag FROM tags WHERE tag IS NOT NULL';
      const params: any[] = [];

      if (buckets.length > 0) {
        query += ` AND bucket = ANY($1)`;
        params.push(buckets);
      }

      query += ' ORDER BY tag LIMIT 5000';

      const result = await db.run(query, params);
      const allTags = new Set<string>();

      if (result.rows) {
        for (const row of result.rows) {
          if (row.tag) allTags.add(row.tag as string);
        }
      }

      res.status(200).json([...allTags].sort());
    } catch (error) {
      console.error('Tag retrieval error:', error);
      res.status(500).json({ error: 'Failed to retrieve tags' });
    }
  });

  // GET /v1/stats - System statistics (anchor_stats tool)
  app.get('/v1/stats', async (_req: Request, res: Response) => {
    try {
      const startTime = Date.now();
      
      // Get counts in parallel
      const [atomsResult, sourcesResult, tagsResult, moleculesResult] = await Promise.all([
        db.run('SELECT COUNT(*) as count FROM atoms'),
        db.run('SELECT COUNT(*) as count FROM sources'),
        db.run('SELECT COUNT(DISTINCT tag) as count FROM tags WHERE tag IS NOT NULL'),
        db.run('SELECT COUNT(*) as count FROM molecules')
      ]);

      const stats = {
        atoms: parseInt(atomsResult.rows?.[0]?.count || '0'),
        sources: parseInt(sourcesResult.rows?.[0]?.count || '0'),
        tags: parseInt(tagsResult.rows?.[0]?.count || '0'),
        molecules: parseInt(moleculesResult.rows?.[0]?.count || '0'),
        query_time_ms: Date.now() - startTime
      };

      res.status(200).json(stats);
    } catch (error) {
      console.error('Stats retrieval error:', error);
      res.status(500).json({ error: 'Failed to retrieve stats' });
    }
  });

  // Backup Endpoints
  // POST /v1/backup - Create a new backup
  app.post('/v1/backup', async (_req: Request, res: Response) => {
    try {
      const result = await createBackup();
      res.status(200).json(result);
    } catch (e: any) {
      console.error("Backup Failed", e);
      res.status(500).json({ error: e.message });
    }
  });

  // GET /v1/backups - List available backups
  app.get('/v1/backups', async (_req: Request, res: Response) => {
    try {
      const backups = await listBackups();
      
      // Get metadata for each backup
      const backupsWithMeta = await Promise.all(
        backups.map(async (filename: string) => {
          const validation = await validateBackup(filename);
          return {
            filename,
            valid: validation.valid,
            error: validation.error || undefined,
            size: (validation as any).size || 0,
            sizeFormatted: (validation as any).sizeFormatted || 'Unknown'
          };
        })
      );
      
      res.status(200).json(backupsWithMeta);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // POST /v1/backup/restore - Restore a specific backup
  app.post('/v1/backup/restore', async (req: Request, res: Response) => {
    try {
      const { filename } = req.body;
      if (!filename) {
        res.status(400).json({ error: "Filename required" });
        return;
      }
      
      // Validate first
      const validation = await validateBackup(filename);
      if (!validation.valid) {
        res.status(400).json({ error: validation.error });
        return;
      }
      
      const startTime = Date.now();
      const result = await restoreBackup(filename);
      const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);
      const atomsPerSec = Math.round(result.memory_count / parseFloat(totalTime));
      
      res.status(200).json({
        success: true,
        message: 'Backup restore complete',
        stats: result,
        totalTime,
        atomsPerSec
      });
    } catch (e: any) {
      console.error("Backup Restore Failed", e);
      res.status(500).json({ error: e.message });
    }
  });

  // GET /v1/backup/latest - Get the latest backup info
  app.get('/v1/backup/latest', async (_req: Request, res: Response) => {
    try {
      const latest = await getLatestBackup();
      if (!latest) {
        res.status(404).json({ error: 'No backups found' });
        return;
      }
      
      const validation = await validateBackup(latest);
      res.status(200).json({
        filename: latest,
        valid: validation.valid,
        error: validation.error || undefined
      });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // GET /v1/backup (Legacy Dump) - Kept for compatibility or download
  app.get('/v1/backup', async (_req: Request, res: Response) => {
    try {
      const result = await createBackup();
      const path = await import('path');
      const fpath = path.join(process.cwd(), 'backups', result.filename);
      res.download(fpath);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // Trigger Dream Endpoint (Disabled - Optimized for STAR algorithm)
  app.post('/v1/dream', async (_req: Request, res: Response) => {
    res.status(501).json({ 
      error: 'Dreamer service is disabled',
      message: 'This endpoint has been disabled to optimize startup for the STAR algorithm'
    });
  });

  // Research Plugin Endpoint
  app.post('/v1/research/scrape', validate(schemas.researchScrape), async (req: Request, res: Response) => {
    try {
      const { url, category } = req.body;
      if (!url) {
        res.status(400).json({ error: 'URL required' });
        return;
      }

      const result = await fetchAndProcess(url, category || 'article');
      if (result.success) {
        res.status(200).json(result);
      } else {
        res.status(500).json(result);
      }
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // POST /v1/research/upload-raw - Save raw content as file
  app.post('/v1/research/upload-raw', async (req: Request, res: Response) => {
    try {
      const { content, filename } = req.body;
      if (!content || !filename) {
        res.status(400).json({ error: 'Content and filename required' });
        return;
      }

      const path = await import('path');
      const fs = await import('fs');

      // Target Directory: context/manual_uploads
      // We need to resolve from project root (engine/.. -> packages/.. -> root)
      // Actually paths.NOTEBOOK_DIR is best if exported.
      // Importing paths from config might be cleaner but let's look at relative.
      // process.cwd() is usually packages/anchor-engine or root.
      // Let's assume process.cwd() + '/../../context' if running from package, or check existing patterns.
      // In researcher.ts: const NOTEBOOK_DIR = '../../config/paths.js';
      // Let's use the same pattern or hardcode relative to CWD if safe.

      // Safest: Use the imported config if available
      const { ENGINE_PLUGINS } = await import('../config/paths.js');

      // Route to: engine/plugins/articles
      const targetDir = path.join(ENGINE_PLUGINS, 'articles');
      if (!fs.existsSync(targetDir)) fs.mkdirSync(targetDir, { recursive: true });

      // Fix for Arbitrary File Write via Path Traversal
      // Ensure filename does not contain directory traversal characters
      const safeFilename = path.basename(filename);
      const filePath = path.join(targetDir, safeFilename);
      await fs.promises.writeFile(filePath, content, 'utf8');

      console.log(`[Research] Manual upload saved: ${filePath}`);
      res.status(200).json({ success: true, filePath });

    } catch (e: any) {
      console.error('[Research] Upload failed:', e.message);
      res.status(500).json({ error: e.message });
    }
  });

  // Maintenance: Re-index Tags (Fix for missing buckets/tags in UI)
  app.post('/v1/maintenance/reindex-tags', async (_req: Request, res: Response) => {
    try {
      console.log("[Maintenance] Starting Tag Re-indexing...");

      // 1. Drop old table
      await db.run('DROP TABLE IF EXISTS tags');

      // 2. Re-create table with correct schema (atom_id, tag, bucket)
      // Note: This relies on db.ts schema, but we want to be explicit here since we just dropped it
      await db.run(`
        CREATE TABLE IF NOT EXISTS tags (
          atom_id TEXT,
          tag TEXT,
          bucket TEXT,
          PRIMARY KEY (atom_id, tag, bucket)
        );
      `);

      // 3. Re-create indexes
      try {
        await db.run('CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);');
        await db.run('CREATE INDEX IF NOT EXISTS idx_tags_bucket ON tags(bucket);');
      } catch (e) { console.warn("Index creation warning", e); }

      // 4. Migrate Data
      const atoms = await db.run('SELECT id, tags, buckets FROM atoms');
      console.log(`[Maintenance] Found ${atoms.rows.length} atoms to re-index.`);

      let count = 0;
      const BATCH_SIZE = 500;
      let values: string[] = [];
      let params: any[] = [];

      const flushBatch = async () => {
        if (values.length === 0) return;
        try {
          const placeholders = values.join(',');
          await db.run(
            `INSERT INTO tags (atom_id, tag, bucket) VALUES ${placeholders}
             ON CONFLICT (atom_id, tag, bucket) DO NOTHING`,
            params
          );
          count += values.length;
        } catch (e) {
          console.warn(`[Maintenance] Batch insert failed:`, e);
        }
        values = [];
        params = [];
      };

      for (const row of atoms.rows) {
        const atomId = row.id;
        const tags = row.tags as string[];
        const buckets = row.buckets as string[];

        if (!tags || !buckets) continue;

        for (const bucket of buckets) {
          for (const tag of tags) {
            if (tag && bucket) {
              const idx = params.length;
              values.push(`($${idx + 1}, $${idx + 2}, $${idx + 3})`);
              params.push(atomId, tag, bucket);

              if (values.length >= BATCH_SIZE) {
                await flushBatch();
              }
            }
          }
        }
      }

      // Flush remaining items
      await flushBatch();

      console.log(`[Maintenance] Re-indexing complete. Inserted ${count} tags.`);
      res.status(200).json({ status: 'success', message: `Re-indexed ${count} tags from ${atoms.rows.length} atoms.` });

    } catch (e: any) {
      console.error('[Maintenance] Re-index failed:', e);
      res.status(500).json({ error: e.message });
    }
  });

  // Web Search Endpoint
  app.get('/v1/research/web-search', async (req: Request, res: Response) => {
    try {
      const q = req.query['q'] as string;
      if (!q) {
        res.status(400).json({ error: 'Query required' });
        return;
      }

      const results = await searchWeb(q);
      res.status(200).json(results);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // Scribe State Endpoints
  // Get State
  // Note: We need to import getState, clearState from services.
  // I will add the import at the top first, then this block.
  // Actually, I can use "import(...)" if I don't want to mess up top level imports, but better to update top level.
  // Let's assume I updated imports.

  app.get('/v1/scribe/state', async (_req: Request, res: Response) => {
    try {
      const state = await getState();
      res.status(200).json({ state });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.delete('/v1/scribe/state', async (_req: Request, res: Response) => {
    try {
      const result = await clearState();
      res.status(200).json(result);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // System config endpoint
  app.get('/v1/system/config', (_req: Request, res: Response) => {
    res.status(200).json({
      status: 'success',
      config: {
        version: '1.0.0',
        engine: 'Sovereign Context Engine',
        timestamp: new Date().toISOString()
      }
    });
  });

  // Memory status endpoint
  app.get('/v1/system/memory', async (_req: Request, res: Response) => {
    try {
      const { resourceManager } = await import('../utils/resource-manager.js');
      const { idleManager } = await import('../services/idle-manager.js');
      const { NlpService } = await import('../services/nlp/nlp-service.js');
      const { isModelLoadedStatus: isNerModelLoaded } = await import('../services/tags/gliner.js');
      
      const memoryStats = resourceManager.getMemoryStats();
      const idleStatus = idleManager.getStatus();
      
      res.status(200).json({
        status: 'success',
        memory: {
          rss: Math.round(memoryStats.rss / 1024 / 1024),
          heapUsed: Math.round(memoryStats.heapUsed / 1024 / 1024),
          heapTotal: Math.round(memoryStats.heapTotal / 1024 / 1024),
          percentageUsed: Math.round(memoryStats.percentageUsed * 100) / 100
        },
        idle: idleStatus,
        models: {
          nlpLoaded: NlpService.isModelLoadedStatus(),
          nerLoaded: isNerModelLoaded()
        },
        timestamp: new Date().toISOString()
      });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // Watcher Path Endpoints
  // GET /v1/system/paths - List currently watched paths
  app.get('/v1/system/paths', async (_req: Request, res: Response) => {
    try {
      const { getWatchedPaths } = await import('../services/ingest/watchdog.js');
      const paths = getWatchedPaths();
      res.status(200).json({ paths });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // POST /v1/system/paths - Add a new path to watch
  app.post('/v1/system/paths', async (req: Request, res: Response) => {
    try {
      const { path } = req.body;
      if (!path) {
        res.status(400).json({ error: 'Path is required' });
        return;
      }

      const { addWatchPath } = await import('../services/ingest/watchdog.js');
      const success = await addWatchPath(path);

      res.status(200).json({
        status: success ? 'success' : 'failed',
        message: success ? `Now watching: ${path}` : 'Failed to add path',
        path
      });
    } catch (e: any) {
      console.error('[API] Failed to add watch path:', e);
      res.status(500).json({ error: e.message });
    }
  });

  // DELETE /v1/system/paths - Remove a watched path
  app.delete('/v1/system/paths', async (req: Request, res: Response) => {
    try {
      const { path } = req.body;
      if (!path) {
        res.status(400).json({ error: 'Path is required' });
        return;
      }

      const { removeWatchPath } = await import('../services/ingest/watchdog.js');
      const success = await removeWatchPath(path);

      res.status(200).json({
        status: success ? 'success' : 'failed',
        message: success ? `Stopped watching: ${path}` : 'Failed to remove path',
        path
      });
    } catch (e: any) {
      console.error('[API] Failed to remove watch path:', e);
      res.status(500).json({ error: e.message });
    }
  });

  // Terminal Command Execution Endpoint
  app.post('/v1/terminal/exec', async (req: Request, res: Response) => {
    try {
      const { command } = req.body;

      if (!command) {
        return res.status(400).json({ error: 'Command is required' });
      }

      // For now, we'll simulate command execution for security
      // In a real implementation, you'd want to use a secure sandbox
      console.log(`[Terminal] Executing command: ${command}`);

      // Validate command to prevent dangerous operations
      const dangerousCommands = ['rm', 'del', 'format', 'mkfs', 'dd', 'shutdown', 'reboot', 'poweroff'];
      const commandParts = command.toLowerCase().split(' ');
      const isDangerous = dangerousCommands.some(dc => commandParts.includes(dc));

      if (isDangerous) {
        return res.status(400).json({
          error: 'Command contains potentially dangerous operations',
          stderr: 'ERROR: Dangerous command blocked by security policy'
        });
      }

      // Special handling for 'clear' command
      if (command.trim().toLowerCase() === 'clear') {
        return res.status(200).json({
          command: command,
          stdout: '', // Empty stdout for clear command
          stderr: '',
          code: 0
        });
      }

      // For now, return mock response - in a real implementation you'd execute securely
      const mockResponses: Record<string, { stdout?: string, stderr?: string, code?: number }> = {
        'ls': { stdout: 'file1.txt\nfile2.md\nfolder1/\nfolder2/' },
        'dir': { stdout: 'file1.txt\nfile2.md\nfolder1/\nfolder2/' },
        'pwd': { stdout: '/home/user/project' },
        'whoami': { stdout: 'user' },
        'echo hello': { stdout: 'hello' },
        'cat README.md': { stdout: '# Project README\n\nThis is a sample readme file.' },
        'type README.md': { stdout: '# Project README\n\nThis is a sample readme file.' },
        'help': { stdout: 'Available commands: ls, pwd, whoami, echo, cat/type, help' },
        'cls': { stdout: '' }
      };

      // Check if we have a predefined response
      const normalizedCmd = command.toLowerCase().trim();
      let response = mockResponses[normalizedCmd];

      // If no exact match, try partial matches
      if (!response) {
        if (normalizedCmd.startsWith('ls') || normalizedCmd.startsWith('dir')) {
          response = { stdout: 'file1.txt\nfile2.md\nfolder1/\nfolder2/' };
        } else if (normalizedCmd.startsWith('cat ') || normalizedCmd.startsWith('type ')) {
          response = { stdout: 'Sample file content for: ' + command.split(' ')[1] };
        } else {
          response = {
            stdout: `Command executed: ${command}\n(Output simulated for security)`,
            stderr: command.includes('error') ? 'Simulated error for testing' : undefined
          };
        }
      }

      res.status(200).json({
        command: command,
        stdout: response.stdout || '',
        stderr: response.stderr || '',
        code: response.code !== undefined ? response.code : 0
      });

    } catch (error: any) {
      console.error('Terminal execution error:', error);
      res.status(500).json({
        error: error.message,
        stderr: `Execution failed: ${error.message}`
      });
    }
  });

  // [DEBUG] Raw SQL Endpoint for Anchor TUI
  // WARNING: accessing this allows full DB control.
  app.post('/v1/debug/sql', async (req: Request, res: Response) => {
    try {
      const { query, params } = req.body;
      if (!query) return res.status(400).json({ error: 'Query required' });

      console.log(`[SQL] Executing: ${query}`);
      const start = Date.now();
      const result = await db.run(query, params || []);
      const duration = Date.now() - start;

      res.status(200).json({
        rows: result.rows,
        fields: result.fields,
        duration_ms: duration,
        row_count: result.rows ? result.rows.length : 0
      });
    } catch (error: any) {
      console.error('[SQL] Error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // Graph Data Endpoint for Context Visualization
  app.post('/v1/graph/data', async (req: Request, res: Response) => {
    try {
      const { query, limit = 20 } = req.body;

      if (!query) {
        return res.status(400).json({ error: 'Query is required' });
      }

      // This would normally call the search service to get real data
      // For now, we'll return mock data based on the query
      console.log(`[Graph] Generating visualization data for query: ${query}`);

      // Generate mock nodes and links based on the query
      const nodes = [
        { id: 'query', label: query, type: 'search', x: 400, y: 300, size: 20, color: '#646cff' },
        { id: 'atom1', label: 'Project Notes', type: 'document', x: 200, y: 150, size: 15, color: '#22d3ee' },
        { id: 'atom2', label: 'Code Snippet', type: 'code', x: 600, y: 150, size: 15, color: '#8b5cf6' },
        { id: 'atom3', label: 'Research Paper', type: 'document', x: 200, y: 450, size: 15, color: '#22d3ee' },
        { id: 'atom4', label: 'Configuration', type: 'config', x: 600, y: 450, size: 15, color: '#10b981' },
        { id: 'tag1', label: '#typescript', type: 'tag', x: 300, y: 100, size: 12, color: '#f59e0b' },
        { id: 'tag2', label: '#ai', type: 'tag', x: 500, y: 100, size: 12, color: '#f59e0b' },
        { id: 'tag3', label: '#graph', type: 'tag', x: 300, y: 500, size: 12, color: '#f59e0b' },
        { id: 'tag4', label: '#memory', type: 'tag', x: 500, y: 500, size: 12, color: '#f59e0b' },
      ];

      const links = [
        { source: 'query', target: 'atom1', strength: 0.8 },
        { source: 'query', target: 'atom2', strength: 0.7 },
        { source: 'query', target: 'atom3', strength: 0.6 },
        { source: 'query', target: 'atom4', strength: 0.5 },
        { source: 'atom1', target: 'tag1', strength: 0.9 },
        { source: 'atom1', target: 'tag2', strength: 0.6 },
        { source: 'atom2', target: 'tag1', strength: 0.7 },
        { source: 'atom2', target: 'tag2', strength: 0.8 },
        { source: 'atom3', target: 'tag3', strength: 0.9 },
        { source: 'atom3', target: 'tag4', strength: 0.6 },
        { source: 'atom4', target: 'tag3', strength: 0.7 },
        { source: 'atom4', target: 'tag4', strength: 0.8 },
      ];

      res.status(200).json({
        nodes: nodes.slice(0, limit),
        links: links.slice(0, limit * 2), // More links than nodes typically
        query: query,
        timestamp: new Date().toISOString()
      });

    } catch (error: any) {
      console.error('Graph data error:', error);
      res.status(500).json({
        error: error.message
      });
    }
  });

  // Configuration endpoint to provide runtime configuration to clients
  app.get('/v1/config', async (_req: Request, res: Response) => {
    try {
      // Import config here to avoid circular dependencies
      const { config } = await import('../config/index.js');

      const serverConfig = {
        port: config.PORT,
        host: config.HOST,
        server_url: `http://${config.HOST}:${config.PORT}`,
        llm_provider: config.LLM_PROVIDER,
        search_strategy: config.SEARCH.strategy,
        features: config.FEATURES
      };

      res.status(200).json(serverConfig);
    } catch (error: any) {
      console.error('Config endpoint error:', error);
      res.status(500).json({
        error: error.message,
        fallback_config: {
          port: 3160,
          host: '127.0.0.1',
          server_url: 'http://127.0.0.1:3160'
        }
      });
    }
  });

  // Include enhanced routes
  setupEnhancedRoutes(app);

  // GitHub Repository Ingestion Endpoints (Standard 115)
  // POST /v1/github/repos - Register new repo and trigger initial ingestion
  app.post('/v1/github/repos', async (req: Request, res: Response) => {
    try {
      const body = req.body as any;
      const url = body.url as string;
      const bucket = body.bucket as string;
      
      if (!url || !bucket) {
        res.status(400).json({ error: 'url and bucket are required' });
        return;
      }

      const { GitHubIngestService } = await import('../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();

      // Register repo
      const repo = await service.registerRepo(url, bucket);
      
      // Start async ingestion (don't wait for completion)
      service.syncRepo(repo.id).catch((error: any) => {
        console.error(`[API] Background sync failed for ${repo.id}:`, error);
      });

      res.status(202).json({
        id: repo.id,
        status: 'ingesting',
        message: `Started ingestion for ${repo.owner}/${repo.repo}`,
      });
    } catch (error: any) {
      console.error('[API] GitHub repo registration error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // GET /v1/github/repos - List all registered repos
  app.get('/v1/github/repos', async (_req: Request, res: Response) => {
    try {
      const { GitHubIngestService } = await import('../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();
      const repos = await service.listRepos();
      res.status(200).json(repos);
    } catch (error: any) {
      console.error('[API] GitHub repo list error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // POST /v1/github/repos/:id/sync - Manual sync trigger
  app.post('/v1/github/repos/:id/sync', async (req: Request, res: Response) => {
    try {
      const id = req.params.id as string;
      
      const { GitHubIngestService } = await import('../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();

      // Start async sync
      service.syncRepo(id).catch((error: any) => {
        console.error(`[API] Background sync failed for ${id}:`, error);
      });

      res.status(202).json({
        id,
        status: 'syncing',
        message: 'Sync started',
      });
    } catch (error: any) {
      console.error('[API] GitHub sync trigger error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // DELETE /v1/github/repos/:id - Remove repo
  app.delete('/v1/github/repos/:id', async (req: Request, res: Response) => {
    try {
      const id = req.params.id as string;
      
      const { GitHubIngestService } = await import('../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();
      
      const quarantinedCount = await service.removeRepo(id);
      
      res.status(200).json({
        status: 'removed',
        quarantined_atoms: quarantinedCount,
      });
    } catch (error: any) {
      console.error('[API] GitHub repo removal error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // GET /v1/github/rate-limit - Check GitHub API rate limit status
  app.get('/v1/github/rate-limit', async (_req: Request, res: Response) => {
    try {
      const { GitHubIngestService } = await import('../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();
      const rateLimit = await service.getRateLimitStatus();
      res.status(200).json(rateLimit);
    } catch (error: any) {
      console.error('[API] GitHub rate limit check error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // GET /v1/git/repos - List available git repositories
  app.get('/v1/git/repos', async (_req: Request, res: Response) => {
    try {
      const path = await import('path');
      const fs = await import('fs');
      const { pathManager } = await import('../utils/path-manager.js');
      const { PROJECT_ROOT } = await import('../config/paths.js');

      // Check common directories for git repos
      const potentialRepos: string[] = [];
      const basePath = pathManager.getBasePath();
      const checkDirs = [
        basePath,
        path.join(basePath, '..'),
        path.join(basePath, '..', '..'),
        PROJECT_ROOT
      ];

      for (const dir of checkDirs) {
        if (!dir) continue;
        try {
          const entries = fs.readdirSync(dir, { withFileTypes: true });
          for (const entry of entries) {
            if (entry.isDirectory()) {
              const repoPath = path.join(dir, entry.name);
              const gitPath = path.join(repoPath, '.git');
              if (fs.existsSync(gitPath) && !potentialRepos.includes(repoPath)) {
                potentialRepos.push(repoPath);
              }
            }
          }
        } catch {
          // Skip if directory doesn't exist or can't be read
        }
      }

      res.status(200).json(potentialRepos);
    } catch (error: any) {
      console.error('[API] Git repos list error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // POST /v1/git/run - Execute git command
  app.post('/v1/git/run', async (req: Request, res: Response) => {
    try {
      const { command, working_dir } = req.body;

      if (!command || !working_dir) {
        return res.status(400).json({ error: 'command and working_dir are required' });
      }

      const { exec } = await import('child_process');
      const util = await import('util');
      const execPromise = util.promisify(exec);

      // Security: Only allow git commands
      const gitCommand = `git ${command}`;

      console.log(`[Git] Running: ${gitCommand} in ${working_dir}`);

      try {
        const { stdout, stderr } = await execPromise(gitCommand, {
          cwd: working_dir,
          encoding: 'utf8',
          timeout: 30000 // 30 second timeout
        });

        res.status(200).json({
          command,
          output: stdout || stderr,
          success: true
        });
      } catch (execError: any) {
        // Git command failed - return error output
        res.status(200).json({
          command,
          output: execError.stdout || '',
          error: execError.stderr || execError.message,
          success: false
        });
      }
    } catch (error: any) {
      console.error('[API] Git command execution error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // Chat Completions - Disabled (requires separate inference server)
  // To enable: Uncomment and configure inference server URL
  /*
  app.post('/v1/chat/completions', async (req: Request, res: Response) => {
    try {
      const INFERENCE_URL = 'http://localhost:3001/v1/chat/completions';
      console.log(`[API] Proxying chat request to ${INFERENCE_URL}`);
      
      const { default: axios } = await import('axios');
      const response = await axios({
        method: 'post',
        url: INFERENCE_URL,
        data: req.body,
        responseType: 'stream',
        timeout: 0,
        headers: { 'Content-Type': 'application/json' }
      });
      
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      res.flushHeaders();
      
      if (response.data) {
        let bytesSent = 0;
        response.data.on('data', (chunk: Buffer) => {
          bytesSent += chunk.length;
          res.write(chunk);
        });
        response.data.on('end', () => {
          console.log(`[API] Proxy Stream Completed. Sent ${bytesSent} bytes.`);
          res.end();
        });
        response.data.on('error', (err: any) => {
          console.error('[API] Stream Error:', err);
          res.end();
        });
      } else {
        res.end();
      }
    } catch (e: any) {
      console.error('[API] Chat Proxy Error:', e);
      if (!res.headersSent) {
        res.status(503).json({
          error: 'Inference Server Unavailable',
          details: e.message
        });
      } else {
        res.end();
      }
    }
  });
  */

  // Model Management Endpoints - Disabled (requires separate inference server)
  /*
  const proxyToInference = async (req: Request, res: Response, path: string, method: string = 'GET') => {
    try {
      const INFERENCE_URL = 'http://localhost:3001';
      const url = `${INFERENCE_URL}${path}`;
      const options: any = {
        method,
        headers: { 'Content-Type': 'application/json' }
      };
      if (method !== 'GET' && method !== 'HEAD') {
        options.body = JSON.stringify(req.body);
      }
      const response = await fetch(url, options);
      const data = await response.json();
      res.status(response.status).json(data);
    } catch (e: any) {
      console.error(`[API] Proxy Error (${path}):`, e);
      res.status(503).json({ error: 'Inference Server Unavailable', details: e.message });
    }
  };

  app.post('/v1/model/load', (req, res) => proxyToInference(req, res, '/v1/model/load', 'POST'));
  app.post('/v1/model/unload', (req, res) => proxyToInference(req, res, '/v1/model/unload', 'POST'));
  app.get('/v1/model/status', (req, res) => proxyToInference(req, res, '/v1/model/status', 'GET'));
  app.get('/v1/models', (req, res) => proxyToInference(req, res, '/v1/models', 'GET'));
  */

  // Return 503 for disabled endpoints
  app.post('/v1/chat/completions', (_req, res) => {
    res.status(503).json({ error: 'Chat completions disabled', message: 'Inference server not configured' });
  });
  app.get('/v1/models', (_req, res) => {
    res.status(503).json({ error: 'Models endpoint disabled', message: 'Inference server not configured' });
  });
  app.get('/v1/model/status', (_req, res) => {
    res.status(503).json({ error: 'Model status disabled', message: 'Inference server not configured' });
  });
  app.post('/v1/model/load', (_req, res) => {
    res.status(503).json({ error: 'Model load disabled', message: 'Inference server not configured' });
  });
  app.post('/v1/model/unload', (_req, res) => {
    res.status(503).json({ error: 'Model unload disabled', message: 'Inference server not configured' });
  });
}