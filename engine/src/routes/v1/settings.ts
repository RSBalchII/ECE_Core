/**
 * Settings API Routes
 *
 * Provides endpoints for reading and updating user_settings.json
 */

import { Application, Request, Response } from 'express';
import { z } from 'zod';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { config } from '../../config/index.js';
import { PROJECT_ROOT, PATHS } from '../../config/paths.js';
import { settingsUpdateSchema } from '../../schemas/api-schemas.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SETTINGS_PATH = path.join(PROJECT_ROOT, 'user_settings.json');

// Default settings template
const DEFAULT_SETTINGS = {
  server: {
    host: '0.0.0.0',
    port: 3160,
    api_key: ''
  },
  database: {
    // Standard 051: Ephemeral Index.
    // true = wipe PGlite index on each restart (default, safest).
    // false = retain index across restarts (faster startup, risks stale data).
    wipe_on_startup: true
  },
  tagging: {
    modulation_level: 50,
    atom_as_tag: false,
    strict_atom_selection: true,
    blacklist_strictness: 75,
    common_words_filter: true,
    min_tag_length: 3,
    max_tags_per_molecule: 20,
    entity_extraction: {
      enabled: true,
      min_confidence: 0.6,
      categories: ['PERSON', 'ORG', 'PRODUCT', 'EVENT', 'LOCATION']
    }
  },
  search: {
    strategy: 'hybrid',
    hide_years_in_tags: true,
    max_chars_default: 524288,
    max_chars_limit: 2000000,
    fts_window_size: 1500,
    fts_padding: 750
  },
  context: {
    relevance_weight: 0.7,
    recency_weight: 0.3,
    clustering_gap_ms: 900000
  },
  physics: {
    damping_factor: 0.85,
    time_decay_lambda: 0.00001,
    temperature: 0.2,
    gravity_threshold: 0.01,
    walk_radius: 1,
    max_per_hop: 50,
    direct_limit: 5,
    walker_limit: 10
  },
  resource_management: {
    gc_cooldown_ms: 30000,
    max_atoms_in_memory: 10000,
    monitoring_interval_ms: 30000
  },
  watcher: {
    debounce_ms: 2000,
    stability_threshold_ms: 2000,
    extra_paths: []
  },
  // Standard 132: Adaptive Concurrency Control
  // Automatically adjusts parallel processing based on available memory
  adaptive_concurrency: {
    // Environment detection: 'auto', 'low_memory', 'high_memory'
    // 'auto' = detect based on free RAM
    // 'low_memory' = force sequential processing (Termux/mobile)
    // 'high_memory' = force parallel processing (desktop/server)
    environment: 'auto',
    // Memory threshold in MB below which to use sequential processing (default: 2048)
    sequential_threshold_mb: 2048,
    // Memory threshold in MB above which to use full parallel processing (default: 8192)
    parallel_threshold_mb: 8192,
    // Maximum concurrent operations in adaptive mode (default: 5)
    max_concurrency: 5,
    // Batch size for low-memory mode (default: 1)
    low_memory_batch_size: 1,
    // Batch size for high-memory mode (default: 20)
    high_memory_batch_size: 20
  }
};

export function setupSettingsRoutes(app: Application) {
  
  // GET /v1/settings - Get all settings
  app.get('/v1/settings', async (_req: Request, res: Response) => {
    try {
      const settings = JSON.parse(await fs.promises.readFile(SETTINGS_PATH, 'utf-8'));
      res.status(200).json({
        status: 'success',
        settings
      });
    } catch (error: any) {
      res.status(500).json({
        status: 'error',
        error: `Failed to read settings: ${error.message}`
      });
    }
  });

  // PUT /v1/settings - Update all settings
  app.put('/v1/settings', async (req: Request, res: Response) => {
    // Validate request body with Zod
    const validation = settingsUpdateSchema.safeParse(req.body);
    if (!validation.success) {
      return res.status(400).json({
        error: 'Invalid settings update',
        details: validation.error.issues.map(e => ({
          field: e.path.join('.'),
          message: e.message
        }))
      });
    }

    try {
      const newSettings = validation.data;
      
      // Validate settings structure
      if (!newSettings || typeof newSettings !== 'object') {
        return res.status(400).json({
          status: 'error',
          error: 'Invalid settings format'
        });
      }

      // Write to file
      fs.writeFileSync(SETTINGS_PATH, JSON.stringify(newSettings, null, 4), 'utf-8');
      
      res.status(200).json({
        status: 'success',
        message: 'Settings updated successfully'
      });
    } catch (error: any) {
      res.status(500).json({
        status: 'error',
        error: `Failed to write settings: ${error.message}`
      });
    }
  });

  // PUT /v1/settings/:category - Update specific category
  app.put('/v1/settings/:category', async (req: Request, res: Response) => {
    try {
      const category = Array.isArray(req.params.category) ? req.params.category[0] : req.params.category;
      const newCategorySettings = req.body;

      // Read current settings
      const settings: any = JSON.parse(await fs.promises.readFile(SETTINGS_PATH, 'utf-8'));

      // Update specific category
      settings[category] = {
        ...settings[category],
        ...newCategorySettings
      };

      // Write back
      fs.writeFileSync(SETTINGS_PATH, JSON.stringify(settings, null, 4), 'utf-8');

      res.status(200).json({
        status: 'success',
        message: `${category} settings updated`,
        settings: settings[category]
      });
    } catch (error: any) {
      res.status(500).json({
        status: 'error',
        error: `Failed to update settings: ${error.message}`
      });
    }
  });

  // GET /v1/settings/defaults - Get default settings
  app.get('/v1/settings/defaults', (_req: Request, res: Response) => {
    res.status(200).json({
      status: 'success',
      settings: DEFAULT_SETTINGS
    });
  });

  // POST /v1/settings/reset - Reset to defaults
  app.post('/v1/settings/reset', async (req: Request, res: Response) => {
    try {
      fs.writeFileSync(SETTINGS_PATH, JSON.stringify(DEFAULT_SETTINGS, null, 4), 'utf-8');

      res.status(200).json({
        status: 'success',
        message: 'Settings reset to defaults'
      });
    } catch (error: any) {
      res.status(500).json({
        status: 'error',
        error: `Failed to reset settings: ${error.message}`
      });
    }
  });

  // GET /v1/settings/paths - Get auto-discovered file paths (Standard 051)
  // Returns universal paths based on project root, no hardcoded values
  app.get('/v1/settings/paths', async (_req: Request, res: Response) => {
    try {
      res.status(200).json({
        status: 'success',
        paths: {
          project_root: PROJECT_ROOT,
          inbox: PATHS.INBOX_DIR,
          external_inbox: PATHS.EXTERNAL_INBOX_DIR,
          mirrored_brain: PATHS.MIRRORED_BRAIN_DIR,
          backups: PATHS.BACKUPS_DIR,
          logs: PATHS.LOGS_DIR,
          database: PATHS.DATABASE_FILE,
          user_settings: PATHS.USER_SETTINGS
        }
      });
    } catch (error: any) {
      res.status(500).json({
        status: 'error',
        error: `Failed to discover paths: ${error.message}`
      });
    }
  });
}
