/**
 * API Routes for Sovereign Context Engine
 *
 * Thin orchestrator that delegates to per-resource route modules in routes/v1/.
 * Each module registers its own routes on the Express app.
 */

import type { Application } from 'express';
import { setupSearchRoutes } from './v1/search.js';
import { setupIngestRoutes } from './v1/ingest.js';
import { setupBackupRoutes } from './v1/backup.js';
import { setupAtomRoutes } from './v1/atoms.js';
import { setupTagsRoutes } from './v1/tags.js';
import { setupGitRoutes } from './v1/git.js';
import { setupResearchRoutes } from './v1/research.js';
import { setupAdminRoutes } from './v1/admin.js';
import { setupSystemRoutes } from './v1/system.js';
import { setupSettingsRoutes } from './v1/settings.js';
import { setupEnhancedRoutes } from './enhanced-api.js';
import { setupMemoryRoutes } from './v1/memory.js';
import { setupDistillRoutes } from './v1/distills.js';
import { setupEncryptionRoutes } from './v1/encryption.js';
import { setupHealthRoutes } from './health.js';
import { registerTestRoutes } from './test-ui.js';
import { setupStatsRoutes } from './v1/stats.js';
import { setupMoleculesRoutes } from './v1/molecules.js';

export function setupRoutes(app: Application) {
  // Health check (must be first — used by load balancers & monitoring)
  setupHealthRoutes(app);

  // Core data routes
  setupSearchRoutes(app);
  setupIngestRoutes(app);
  setupBackupRoutes(app);
  setupAtomRoutes(app);
  setupTagsRoutes(app);

  // Encryption routes (must be before system routes)
  setupEncryptionRoutes(app);

  // Molecules routes (post-Standard 051 migration)
  setupMoleculesRoutes(app);

  // System & admin routes (includes /v1/stats, /health, watchdog endpoints)
  setupSystemRoutes(app);
  setupSettingsRoutes(app);
  setupAdminRoutes(app);

  // Stats endpoint
  setupStatsRoutes(app);

  // External integrations
  setupGitRoutes(app);
  setupResearchRoutes(app);

  // Enhanced/experimental routes
  setupEnhancedRoutes(app);
  setupMemoryRoutes(app);
  setupDistillRoutes(app);

  // Test UI routes
  registerTestRoutes(app);
}