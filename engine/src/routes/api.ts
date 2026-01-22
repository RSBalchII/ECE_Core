/**
 * API Routes for Sovereign Context Engine
 * 
 * Standardized API Interface implementing UniversalRAG architecture.
 */

import { Application, Request, Response } from 'express';
import * as crypto from 'crypto';
import { db } from '../core/db.js';

// Import services and types
import { executeSearch } from '../services/search/search.js';
import { dream } from '../services/dreamer/dreamer.js';
import { getState, clearState } from '../services/scribe/scribe.js';
import { listModels, loadModel, runSideChannel } from '../services/llm/provider.js';
import { createBackup, listBackups, restoreBackup } from '../services/backup/backup.js';
import { SearchRequest } from '../types/api.js';

export function setupRoutes(app: Application) {
  // Ingestion endpoint
  app.post('/v1/ingest', async (req: Request, res: Response) => {
    try {
      const { content, source, type, bucket, buckets = [], tags = [] } = req.body;

      if (!content) {
        res.status(400).json({ error: 'Content is required' });
        return;
      }

      // Handle legacy single-bucket param
      const allBuckets = bucket ? [...buckets, bucket] : buckets;

      // Generate a unique ID for the memory
      const id = `mem_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const timestamp = Date.now();
      const hash = crypto.createHash('sha256').update(content).digest('hex');

      // Insert into the database
      console.log(`[API] Ingesting memory: ${id} (Source: ${source || 'unknown'})`);
      // Schema: id => timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding
      await db.run(
        `?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, tags, epochs, provenance, embedding] <- $data 
         :insert memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, tags, epochs, provenance, embedding}`,
        {
          data: [[
            id,
            timestamp,
            content,
            source || 'unknown',
            source || 'unknown',
            0,
            type || 'text',
            hash,
            allBuckets,
            [], // epochs (aligned with schema)
            tags,
            'external',
            new Array(384).fill(0.0)
          ]]
        }
      );

      // Verification (Standard 059: Read-After-Write)
      // We check for the specific ID we just inserted.
      const verify = await db.run(`?[id] := *memory{id}, id = $id`, { id });
      const count = verify.rows ? verify.rows.length : 0;

      console.log(`[API] VERIFY ID ${id}: Found ${count}`);

      if (count === 0) {
        throw new Error(`Ingestion Verification Failed: ID ${id} not found after write.`);
      }

      try {
        const fs = await import('fs');
        const path = await import('path');
        const logPath = path.join(process.cwd(), 'debug_force.log');
        fs.appendFileSync(logPath, `[${new Date().toISOString()}] Ingest Success: ${id} | Count: ${count}\n`);
        console.log(`[API] Logged to ${logPath}`);
      } catch (e) {
        console.error('[API] Log Write Failed', e);
      }

      res.status(200).json({
        status: 'success',
        id,
        message: 'Content ingested successfully'
      });
    } catch (error: any) {
      console.error('Ingestion error:', error);
      res.status(500).json({ error: 'Failed to ingest content', details: error.message });
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
      const check = await db.run(`?[tags] := *memory{id, tags}, id = $id`, { id });
      if (!check.rows || check.rows.length === 0) {
        res.status(404).json({ error: 'Atom not found' });
        return;
      }

      const currentTags = check.rows[0][0] as string[];
      const newTags = [...new Set([...currentTags, '#manually_quarantined'])];

      // 2. Update Record (CozoDB :put overwrites existing key)
      // We only update provenance and tags. Other fields remain same?
      // No, :put replaces the whole tuple. We must read ALL fields first.

      const fullRecord = await db.run(`?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding] := *memory{id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding}, id = $id`, { id });

      if (!fullRecord.rows || fullRecord.rows.length === 0) {
        res.status(500).json({ error: 'Read-Modify-Write failed' });
        return;
      }

      const row = fullRecord.rows[0];
      // row indices: 0:id, 1:ts, 2:content, 3:source, 4:sid, 5:seq, 6:type, 7:hash, 8:buckets, 9:epochs, 10:tags, 11:provenance, 12:embedding

      const updatedRow = [...row];
      updatedRow[10] = newTags;      // Update Tags
      updatedRow[11] = 'quarantine'; // Update Provenance

      await db.run(
        `?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding] <- $data 
         :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding}`,
        { data: [updatedRow] }
      );

      res.status(200).json({ status: 'success', message: `Atom ${id} quarantined.` });

    } catch (e: any) {
      console.error(`[API] Quarantine Failed: ${e.message}`);
      res.status(500).json({ error: e.message });
    }
  });

  // POST Search endpoint (Standard UniversalRAG)
  app.post('/v1/memory/search', async (req: Request, res: Response) => {
    try {
      const body = req.body as SearchRequest;
      if (!body.query) {
        res.status(400).json({ error: 'Query is defined' });
        return;
      }

      // Map request to executeSearch args
      const result = await executeSearch(
        body.query,
        undefined,
        body.buckets,
        body.max_chars || 5000,
        body.deep || false,
        body.provenance || 'all'
      );

      // Construct standard response
      res.status(200).json({
        status: 'success',
        context: result.context,
        results: result.results,
        metadata: {
          engram_hits: 0,
          vector_latency: 0,
          provenance_boost_active: true,
          ...(result.metadata || {})
        }
      });
    } catch (error: any) {
      console.error('Search error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // GET Search (Legacy support) - redirect to use POST effectively
  app.get('/v1/memory/search', async (_req: Request, res: Response) => {
    res.status(400).json({ error: "Use POST /v1/memory/search for complex queries." });
  });

  // Get all buckets
  app.get('/v1/buckets', async (_req: Request, res: Response) => {
    try {
      const result = await db.run('?[bucket] := *memory{buckets}, bucket in buckets');
      const buckets = result.rows ? [...new Set(result.rows.map((row: any) => row[0]))].sort() : [];
      res.status(200).json(buckets);
    } catch (error) {
      console.error('Bucket retrieval error:', error);
      res.status(500).json({ error: 'Failed to retrieve buckets' });
    }
  });

  // Get all tags
  app.get('/v1/tags', async (_req: Request, res: Response) => {
    try {
      const result = await db.run('?[tag] := *memory{tags}, tag in tags');
      const tags = result.rows ? [...new Set(result.rows.map((row: any) => row[0]))].sort() : [];
      res.status(200).json(tags);
    } catch (error) {
      console.error('Tag retrieval error:', error);
      res.status(500).json({ error: 'Failed to retrieve tags' });
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
      const result = await listBackups();
      res.status(200).json(result);
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
      const result = await restoreBackup(filename);
      res.status(200).json(result);
    } catch (e: any) {
      console.error("Restore Failed", e);
      res.status(500).json({ error: e.message });
    }
  });

  // GET /v1/backup (Legacy Dump) - Kept for compatibility or download
  // Modifying to use createBackup logic but stream result?
  // Current createBackup writes to disk.
  // Let's redirect to disk file download if needed, or keep previous logic.
  // The user wanted "Save to server".
  // Let's keep the GET for downloading the LATEST backup or generating one on fly?
  // Let's make GET just return text of latest? Or generate on fly?
  // Let's generate on fly like before for "Dump".
  app.get('/v1/backup', async (_req: Request, res: Response) => {
    // Return ID of new backup? Or stream content?
    // Legacy behavior was stream content.
    try {
      const result = await createBackup();
      const path = await import('path');
      // const fs = await import('fs'); // Unused
      const fpath = path.join(process.cwd(), 'backups', result.filename);
      res.download(fpath);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // Trigger Dream Endpoint
  app.post('/v1/dream', async (_req: Request, res: Response) => {
    try {
      const result = await dream();
      res.status(200).json(result);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // LLM: List Models
  app.get('/v1/models', async (req: Request, res: Response) => {
    try {
      const dir = req.query['dir'] as string | undefined;
      const models = await listModels(dir);
      res.status(200).json(models);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // LLM: Load Model
  app.post('/v1/inference/load', async (req: Request, res: Response) => {
    try {
      const { model, options, dir } = req.body; // dir optional, used to construct absolute path if model is just filename?
      if (!model) {
        res.status(400).json({ error: "Model name required" });
        return;
      }

      // If dir provided and model is not absolute, join them
      const path = await import('path');
      let modelPath = model;
      if (dir && !path.isAbsolute(model)) {
        modelPath = path.join(dir, model);
      }

      const result = await loadModel(modelPath, options);
      res.status(200).json(result);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // LLM: Chat Completions (SSE Streaming)
  app.post('/v1/chat/completions', async (req: Request, res: Response) => {
    try {
      const { messages, options } = req.body;
      const lastMsg = messages[messages.length - 1];
      const prompt = lastMsg.content;

      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');

      const fullResponse = (await runSideChannel(prompt, "You are a helpful AI.", options)) as string | null;

      if (!fullResponse) {
        res.write(`data: ${JSON.stringify({ error: "No response from model" })}\n\n`);
        res.end();
        return;
      }

      // Simulate streaming by chunks
      // Simulate streaming by chunks
      const chunkSize = 20;
      for (let i = 0; i < fullResponse.length; i += chunkSize) {
        const chunk = fullResponse.substring(i, i + chunkSize);
        const packet = {
          choices: [{
            delta: { content: chunk }
          }]
        };
        res.write(`data: ${JSON.stringify(packet)}\n\n`);
        await new Promise(r => setTimeout(r, 10));
      }

      res.write('data: [DONE]\n\n');
      res.end();

    } catch (e: any) {
      console.error("Chat Error", e);
      res.write(`data: ${JSON.stringify({ error: e.message })}\n\n`);
      res.end();
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
}