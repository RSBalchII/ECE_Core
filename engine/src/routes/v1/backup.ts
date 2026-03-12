import { Application, Request, Response } from 'express';
import * as path from 'path';
import { createBackup, listBackups, restoreBackup } from '../../services/backup/backup.js';
import { getLatestBackup, validateBackup } from '../../services/backup/backup-restore.js';

export function setupBackupRoutes(app: Application) {
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

      // Prevent directory traversal attacks by ensuring only the basename is used
      const safeFilename = path.basename(filename);

      // Validate first
      const validation = await validateBackup(safeFilename);
      if (!validation.valid) {
        res.status(400).json({ error: validation.error });
        return;
      }

      const startTime = Date.now();
      const result = await restoreBackup(safeFilename);
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
}
