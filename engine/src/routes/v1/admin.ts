import { Application, Request, Response } from 'express';
import { db } from '../../core/db.js';

export function setupAdminRoutes(app: Application) {
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

  // Trigger Dream Endpoint (Disabled - Optimized for STAR algorithm)
  app.post('/v1/dream', async (_req: Request, res: Response) => {
    res.status(501).json({
      error: 'Dreamer service is disabled',
      message: 'This endpoint has been disabled to optimize startup for the STAR algorithm'
    });
  });

  // Return 503 for disabled inference endpoints
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
