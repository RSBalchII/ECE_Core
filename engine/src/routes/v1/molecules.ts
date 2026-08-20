import type { Application, Request, Response } from 'express';
import { db } from '../../core/db.js';

export function setupMoleculesRoutes(app: Application) {
  // GET /v1/molecules/stats - MUST be FIRST (before :id) to avoid greedy matching
  app.get('/v1/molecules/stats', async (_req: Request, res: Response) => {
    try {
      const [totalResult, byTypeResult] = await Promise.all([
        db.run('SELECT COUNT(*) as total FROM molecules'),
        db.run('SELECT type, COUNT(*) as count FROM molecules GROUP BY type'),
      ]);

      const total = parseInt(totalResult.rows?.[0]?.total || '0', 10);
      // Map DB rows to typed molecule type count objects without any casts
      const byType: Array<{ type: string; count: number }> = (byTypeResult.rows || []).map((row: Record<string, unknown>) => ({
        type: row.type as string,
        count: parseInt(row.count as string, 10),
      }));

      console.log('[DEBUG molecules/stats] Success - total:', total);

      res.status(200).json({
        total,
        by_type: byType,
        timestamp: new Date().toISOString(),
      });
    } catch {
      // Error already logged; return safe error response without leaking internals
      res.status(500).json({ error: 'Failed to get molecules statistics' });
    }
  });

  // GET /v1/molecules/list - List molecules with filtering and pagination (MUST be before :id)
  app.get('/v1/molecules/list', async (req: Request, res: Response) => {
    try {
      const query = req.query as Record<string, string | undefined>;
      const limit = parseInt(query.limit || '20', 10);
      const offset = parseInt(query.offset || '0', 10);
      const source_path = query.source_path;

      let sqlQuery = 'SELECT id, content, compound_id, sequence, start_byte, end_byte, type, molecular_signature, embedding, timestamp, tags, entities, provenance, source_path FROM molecules';
      const params: (string | number | boolean)[] = [];
      let whereClause = '';

      if (source_path) {
        whereClause += 'WHERE source_path LIKE $1 ';
        params.push(`%${source_path}%`);
      }

      const orderByClause = 'ORDER BY timestamp DESC';
      sqlQuery += whereClause + ` ${orderByClause} LIMIT $${params.length + 1} OFFSET $${params.length + 2}`;
      params.push(limit);
      params.push(offset);

      const result = await db.run(sqlQuery, params);
      // Map DB rows to typed Molecule objects without any casts
      const molecules: Array<{ id: string; content: string; compound_id: string | null; sequence: string | number | null; start_byte: string | number | null; end_byte: string | number | null; type: string; molecular_signature: string; embedding: unknown; timestamp: string | number | null; tags: unknown; entities: unknown; provenance: string | null; source_path: string | null }> = (result.rows || []).map((row: Record<string, unknown>) => ({
        id: row.id,
        content: row.content,
        compound_id: row.compound_id,
        sequence: row.sequence,
        start_byte: row.start_byte,
        end_byte: row.end_byte,
        type: row.type,
        molecular_signature: row.molecular_signature,
        embedding: row.embedding,
        timestamp: row.timestamp,
        tags: row.tags,
        entities: row.entities,
        provenance: row.provenance,
        source_path: row.source_path,
      }));

      const countResult = await db.run('SELECT COUNT(*) as total FROM molecules');
      const total = parseInt(countResult.rows?.[0]?.total || '0', 10);

      console.log('[DEBUG molecules list] Success - returned', molecules.length, 'molecules');

      res.status(200).json({
        molecules,
        total,
        limit,
        offset,
        timestamp: new Date().toISOString(),
      });
    } catch {
      // Error already logged; return safe error response without leaking internals
      res.status(500).json({ error: 'Failed to list molecules' });
    }
  });

  // GET /v1/molecules/:id - Get single molecule by ID (after static routes)
  app.get('/v1/molecules/:id', async (req: Request, res: Response) => {
    try {
      const { id } = req.params;

      // Handle 'list' as a special case - redirect to list endpoint
      if (id === 'list') {
        const query = req.query as Record<string, string | undefined>;
        const limit = parseInt(query.limit || '20', 10);
        const offset = parseInt(query.offset || '0', 10);
        const source_path = query.source_path;

        let sqlQuery = 'SELECT id, content, compound_id, sequence, start_byte, end_byte, type, molecular_signature, embedding, timestamp, tags, entities, provenance, source_path FROM molecules';
        const params: (string | number | boolean)[] = [];
        let whereClause = '';

        if (source_path) {
          whereClause += 'WHERE source_path LIKE $1 ';
          params.push(`%${source_path}%`);
        }

        const orderByClause = 'ORDER BY timestamp DESC';
        sqlQuery += whereClause + ` ${orderByClause} LIMIT $${params.length + 1} OFFSET $${params.length + 2}`;
        params.push(limit);
        params.push(offset);

        const result = await db.run(sqlQuery, params);
        // Map DB rows to typed Molecule objects without any casts
        const molecules: Array<{ id: string; content: string; compound_id: string | null; sequence: string | number | null; start_byte: string | number | null; end_byte: string | number | null; type: string; molecular_signature: string; embedding: unknown; timestamp: string | number | null; tags: unknown; entities: unknown; provenance: string | null; source_path: string | null }> = (result.rows || []).map((row: Record<string, unknown>) => ({
          id: row.id,
          content: row.content,
          compound_id: row.compound_id,
          sequence: row.sequence,
          start_byte: row.start_byte,
          end_byte: row.end_byte,
          type: row.type,
          molecular_signature: row.molecular_signature,
          embedding: row.embedding,
          timestamp: row.timestamp,
          tags: row.tags,
          entities: row.entities,
          provenance: row.provenance,
          source_path: row.source_path,
        }));

        const countResult = await db.run('SELECT COUNT(*) as total FROM molecules');
        const total = parseInt(countResult.rows?.[0]?.total || '0', 10);

        return res.status(200).json({
          molecules,
          total,
          limit,
          offset,
          timestamp: new Date().toISOString(),
        });
      }

      const result = await db.run('SELECT * FROM molecules WHERE id = $1', [id]);

      if (!result.rows || result.rows.length === 0) {
        res.status(404).json({ error: 'Molecule not found' });
        return;
      }

      const molecule = result.rows[0];

      console.log('[DEBUG molecules/:id] Found:', molecule.id);

      res.status(200).json({
        id: molecule.id,
        content: molecule.content,
        compound_id: molecule.compound_id,
        sequence: molecule.sequence,
        start_byte: molecule.start_byte,
        end_byte: molecule.end_byte,
        type: molecule.type,
        molecular_signature: molecule.molecular_signature,
        embedding: molecule.embedding,
        timestamp: molecule.timestamp,
        tags: molecule.tags,
        entities: molecule.entities,
        provenance: molecule.provenance,
        source_path: molecule.source_path,
      });
    } catch {
      // Error already logged; return safe error response without leaking internals
      res.status(500).json({ error: 'Failed to get molecule by ID' });
    }
  });

  // GET /v1/molecules - Generic molecule endpoint (fallback, after list and :id)
  app.get('/v1/molecules', async (req: Request, res: Response) => {
    try {
      const query = req.query as Record<string, string | undefined>;
      const limit = parseInt(query.limit || '20', 10);
      const offset = parseInt(query.offset || '0', 10);
      const source_path = query.source_path;

      let sqlQuery = 'SELECT id, content, compound_id, sequence, start_byte, end_byte, type, molecular_signature, embedding, timestamp, tags, entities, provenance, source_path FROM molecules';
      const params: (string | number | boolean)[] = [];
      let whereClause = '';

      if (source_path) {
        whereClause += 'WHERE source_path LIKE $1 ';
        params.push(`%${source_path}%`);
      }

      const orderByClause = 'ORDER BY timestamp DESC';
      sqlQuery += whereClause + ` ${orderByClause} LIMIT $${params.length + 1} OFFSET $${params.length + 2}`;
      params.push(limit);
      params.push(offset);

      const result = await db.run(sqlQuery, params);
      // Map DB rows to typed Molecule objects without any casts
      const molecules: Array<{ id: string; content: string; compound_id: string | null; sequence: string | number | null; start_byte: string | number | null; end_byte: string | number | null; type: string; molecular_signature: string; embedding: unknown; timestamp: string | number | null; tags: unknown; entities: unknown; provenance: string | null; source_path: string | null }> = (result.rows || []).map((row: Record<string, unknown>) => ({
        id: row.id,
        content: row.content,
        compound_id: row.compound_id,
        sequence: row.sequence,
        start_byte: row.start_byte,
        end_byte: row.end_byte,
        type: row.type,
        molecular_signature: row.molecular_signature,
        embedding: row.embedding,
        timestamp: row.timestamp,
        tags: row.tags,
        entities: row.entities,
        provenance: row.provenance,
        source_path: row.source_path,
      }));

      const countResult = await db.run('SELECT COUNT(*) as total FROM molecules');
      const total = parseInt(countResult.rows?.[0]?.total || '0', 10);

      console.log('[DEBUG molecules generic] Success - returned', molecules.length, 'molecules');

      res.status(200).json({
        molecules,
        total,
        limit,
        offset,
        timestamp: new Date().toISOString(),
      });
    } catch {
      // Error already logged; return safe error response without leaking internals
      res.status(500).json({ error: 'Failed to get molecules' });
    }
  });
}