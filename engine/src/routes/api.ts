/**
 * API Routes for Sovereign Context Engine
 * 
 * Standardized API Interface implementing UniversalRAG architecture.
 */

import { Application, Request, Response } from 'express';
import * as crypto from 'crypto';
import { db } from '../core/db.js';

// Import services and types
import { executeSearch, smartChatSearch } from '../services/search/search.js';
import { dream } from '../services/dreamer/dreamer.js';
import { getState, clearState } from '../services/scribe/scribe.js';
import { listModels, loadModel, runStreamingChat } from '../services/llm/provider.js';
import { createBackup, listBackups, restoreBackup } from '../services/backup/backup.js';
import { summarizeContext } from '../services/llm/reader.js';
import { fetchAndProcess, searchWeb } from '../services/research/researcher.js';
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
      // Insert into the database
      console.log(`[API] Ingesting memory: ${id} (Source: ${source || 'unknown'})`);
      // Schema: id => timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding
      await db.run(
        `?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, tags, epochs, provenance, simhash, embedding] <- $data 
         :insert memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, tags, epochs, provenance, simhash, embedding}`,
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
            tags,
            [], // epochs
            'external',
            "0", // simhash (default)
            new Array(768).fill(0.0)
          ]]
        }
      );

      // ...

      res.status(200).json({ status: 'success', id, message: 'Ingested successfully' });
    } catch (e: any) {
      console.error('[API] Ingest Error:', e);
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
      const check = await db.run(`?[tags] := *memory{id, tags}, id = $id`, { id });
      if (!check.rows || check.rows.length === 0) {
        res.status(404).json({ error: 'Atom not found' });
        return;
      }

      const currentTags = check.rows[0][0] as string[];
      const newTags = [...new Set([...currentTags, '#manually_quarantined'])];

      // 2. Update Record (CozoDB :put overwrites existing key)
      const fullRecord = await db.run(`?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] := *memory{id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}, id = $id`, { id });

      if (!fullRecord.rows || fullRecord.rows.length === 0) {
        res.status(500).json({ error: 'Read-Modify-Write failed' });
        return;
      }

      const row = fullRecord.rows[0];
      // row indices: 0:id, ..., 10:tags, 11:provenance, 12:simhash, 13:embedding

      const updatedRow = [...row];
      updatedRow[10] = newTags;      // Update Tags
      updatedRow[11] = 'quarantine'; // Update Provenance

      await db.run(
        `?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] <- $data 
         :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}`,
        { data: [updatedRow] }
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
        ?[id, content, source, timestamp, buckets, tags, provenance, simhash, embedding] := 
        *memory{id, content, source, timestamp, buckets, tags, provenance, simhash, embedding},
        provenance = 'quarantine',
        :order -timestamp
        :limit 100
      `;
      const result = await db.run(query);

      const atoms = (result.rows || []).map((row: any[]) => ({
        id: row[0],
        content: row[1],
        source: row[2],
        timestamp: row[3],
        buckets: row[4],
        tags: row[5],
        provenance: row[6],
        simhash: row[7]
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
      const fullRecord = await db.run(`?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] := *memory{id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}, id = $id`, { id });

      if (!fullRecord.rows || fullRecord.rows.length === 0) {
        res.status(404).json({ error: 'Atom not found' });
        return;
      }

      const row = fullRecord.rows[0];
      // row indices: 0:id, ..., 12:simhash, 13:embedding
      const updatedRow = [...row];
      updatedRow[2] = content; // Update Content

      // Update Hash
      updatedRow[7] = crypto.createHash('sha256').update(content).digest('hex');

      // Zero Embedding (Force re-embed)
      updatedRow[13] = new Array(384).fill(0.0); // Index 13 is embedding now

      await db.run(
        `?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] <- $data 
         :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}`,
        { data: [updatedRow] }
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

      const fullRecord = await db.run(`?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] := *memory{id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}, id = $id`, { id });

      if (!fullRecord.rows || fullRecord.rows.length === 0) {
        res.status(404).json({ error: 'Atom not found' });
        return;
      }

      const row = fullRecord.rows[0];
      const currentTags = row[10] as string[];

      // Filter out quarantine tags
      const newTags = currentTags.filter(t => t !== '#manually_quarantined' && t !== '#auto_quarantined');

      const updatedRow = [...row];
      updatedRow[10] = newTags;
      updatedRow[11] = 'internal'; // Mark as Internal

      await db.run(
        `?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] <- $data 
         :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}`,
        { data: [updatedRow] }
      );

      res.status(200).json({ status: 'success', message: `Atom ${id} restored to Graph.` });
    } catch (e: any) {
      // ...
    }
  });

  // POST Search endpoint (Standard UniversalRAG + Iterative Logic)
  app.post('/v1/memory/search', async (req: Request, res: Response) => {
    try {
      const body = req.body as SearchRequest;
      if (!body.query) {
        res.status(400).json({ error: 'Query is required' });
        return;
      }

      // Handle legacy params
      const bucketParam = (req.body as any).bucket;
      const buckets = body.buckets || [];
      const allBuckets = bucketParam ? [...buckets, bucketParam] : buckets;
      const budget = (req.body as any).token_budget ? (req.body as any).token_budget * 4 : (body.max_chars || 20000);

      // Use Smart Search Strategy
      const result = await smartChatSearch(
        body.query,
        allBuckets,
        budget
      );

      // Construct standard response
      console.log(`[API] Search "${body.query}" -> Found ${result.results.length} results (Strategy: ${result.strategy})`);

      res.status(200).json({
        status: 'success',
        context: result.context,
        results: result.results,
        strategy: result.strategy,
        attempt: (result as any).attempt || 1,
        split_queries: result.splitQueries || [],
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

  // Research Plugin Endpoint
  app.post('/v1/research/scrape', async (req: Request, res: Response) => {
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

  // LLM: Chat Completions (Real Streaming + Reasoning Loop)
  app.post('/v1/chat/completions', async (req: Request, res: Response) => {
    try {
      const { messages, temperature = 0.7, max_tokens = 2048 } = req.body;

      // 1. Setup SSE
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      res.flushHeaders();

      // 2. Inject System Prompt
      let systemContent = `You are an intelligent assistant connected to a Sovereign Context Engine.
You have access to a semantic database.
To search for information, output a search query wrapped in tags like this: <search budget="5000">your query here</search>.
The 'budget' attribute (optional, default 5000) controls the max characters of context to retrieve. Use higher budget (e.g. 10000) for broad research, lower (e.g. 2000) for specific facts.
Stop generating after outputting the tag.
When you receive the search results, answer the user's question using that information.`;

      // --- LOGIC LOOP START ---
      // Deterministic "Code-First" Search before the model thinks
      const userMsg = messages[messages.length - 1];
      if (userMsg.role === 'user') {
        // Stream "Thinking" / Logic events
        res.write(`data: ${JSON.stringify({ type: 'tool', status: 'searching', query: userMsg.content, budget: 'Auto' })}\n\n`);

        // 1. Smart Multi-Query Search (Markovian Context)
        const searchRes = await smartChatSearch(userMsg.content, [], 20000); // 20k chars budget

        if (searchRes.results.length > 0) {
          const strategyName = (searchRes as any).strategy || 'standard';
          const foundMsg = `Found ${searchRes.results.length} memories (Strategy: ${strategyName}). Reading...`;
          res.write(`data: ${JSON.stringify({ type: 'tool_result', content: foundMsg, full_context: '[Reading Context...]' })}\n\n`);

          // 2. Summary (Reader Service)
          const summary = await summarizeContext(searchRes.results, userMsg.content);

          // Inject Summary
          systemContent += `\n\nCONTEXT SUMMARY:\n${summary}\n\n(This context was automatically retrieved and summarized. Use it to answer the user.)`;

          // Stream Summary to UI (Visible to User)
          res.write(`data: ${JSON.stringify({ type: 'tool_result', content: 'Context Summarized', full_context: summary })}\n\n`);
        } else {
          // 0 Results
          res.write(`data: ${JSON.stringify({ type: 'tool_result', content: 'No memories found', full_context: 'No relevant memories found in database.' })}\n\n`);
        }
      }
      // --- LOGIC LOOP END ---

      const toolSystemMsg = {
        role: 'system',
        content: systemContent
      };

      const effectiveMessages = [toolSystemMsg, ...messages];
      const MAX_TURNS = 5;
      let turn = 0;

      // 3. Reasoning Loop
      while (turn < MAX_TURNS) {
        turn++;
        console.log(`\n[API] 🔄 Turn ${turn} (Thought Loop)`);

        let bufferedResponse = "";
        let fullPrompt = effectiveMessages.map((msg: any) => {
          const role = msg.role || 'user';
          const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content || '');
          if (role === 'system') return `<|system|>\n${content}`;
          if (role === 'user') return `<|user|>\n${content}`;
          if (role === 'assistant') return `<|assistant|>\n${content}`;
          return `${role.charAt(0).toUpperCase() + role.slice(1)}: ${content}`;
        }).join('\n\n');
        fullPrompt += '\n\n<|assistant|>\n';

        try {
          await runStreamingChat(
            fullPrompt,
            (token: string) => {
              // Stream to client
              const chunk = {
                id: `chatcmpl-${Date.now()}`,
                object: "chat.completion.chunk",
                created: Math.floor(Date.now() / 1000),
                model: "ece-core",
                choices: [{ index: 0, delta: { content: token }, finish_reason: null }]
              };
              res.write(`data: ${JSON.stringify(chunk)}\n\n`);
              bufferedResponse += token;
            },
            "You are a helpful assistant.", // System prompt handled in fullPrompt structure for Qwen
            { temperature, maxTokens: max_tokens }
          );

          console.log(`[API] Turn ${turn} Complete. Output Length: ${bufferedResponse.length}`);

          // 4. Check for Tools (Regex updated for Budget)
          const searchMatch = bufferedResponse.match(/<search(?: budget="(\d+)")?>(.*?)<\/search>/s);
          if (searchMatch) {
            const budget = searchMatch[1] ? parseInt(searchMatch[1]) : 5000;
            const query = searchMatch[2].trim();
            console.log(`[API] 🔍 Tool Call: Search("${query}") | Budget: ${budget}`);

            // Notify Client of Tool Usage (Simulating a "Thought" or "Tool" event)
            res.write(`data: ${JSON.stringify({ type: 'tool', status: 'searching', query, budget })}\n\n`);

            // Execute Search (Internal Function)
            const searchResult = await executeSearch(query, undefined, undefined, budget, false, 'all');

            let toolOutput = "";
            let toolDisplay = ""; // Concise version for UI

            if (searchResult.results.length > 0) {
              toolDisplay = `Found ${searchResult.results.length} memories (Total ${searchResult.context.length} chars).`;
              toolOutput = `[Found ${searchResult.results.length} memories]:\n` +
                searchResult.results.map(r => `- (${new Date(r.timestamp).toISOString()}) ${r.content.substring(0, 150)}...`).join('\n');
            } else {
              toolDisplay = `No memories found.`;
              toolOutput = `[No memories found for "${query}"]`;
            }

            // Stream Result to Client
            res.write(`data: ${JSON.stringify({ type: 'tool_result', content: toolDisplay, full_context: toolOutput })}\n\n`);

            // Append to context
            effectiveMessages.push({ role: 'assistant', content: bufferedResponse });
            effectiveMessages.push({ role: 'system', content: `TOOL OUTPUT: ${toolOutput}\nNow answer.` });

            // Continue Loop
            continue;

          } else {
            // No tool call -> Done
            break;
          }

        } catch (streamingError: any) {
          console.error("[API] Streaming Error:", streamingError);
          res.write(`data: ${JSON.stringify({ error: streamingError.message })}\n\n`);
          // Force break loop
          break;
        }
      }

      // 5. Finish
      res.write('data: [DONE]\n\n');
      res.end();

    } catch (e: any) {
      console.error("Chat API Error", e);
      if (!res.headersSent) res.status(500).json({ error: e.message });
      else res.end();
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