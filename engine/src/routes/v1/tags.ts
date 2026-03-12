import { Application, Request, Response } from 'express';
import { z } from 'zod';
import { db } from '../../core/db.js';
import { bucketCreateSchema } from '../../schemas/api-schemas.js';

export function setupTagsRoutes(app: Application) {
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
    // Validate request body with Zod
    const validation = bucketCreateSchema.safeParse(req.body);
    if (!validation.success) {
      return res.status(400).json({
        error: 'Invalid bucket request',
        details: validation.error.issues.map(e => ({
          field: e.path.join('.'),
          message: e.message
        }))
      });
    }

    try {
      const { name, location } = validation.data;

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
        `INSERT INTO tags (atom_id, tag, bucket) VALUES ($1, $2, $3)
         ON CONFLICT (atom_id, tag, bucket) DO NOTHING`,
        ['__system__', placeholderTag, bucketName]
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
}
