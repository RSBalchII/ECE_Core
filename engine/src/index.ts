// engine/src/index.ts
import express from 'express';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import path from 'path';
import { existsSync, rmSync, readdirSync, statSync, appendFileSync, mkdirSync } from 'fs';
import { fileURLToPath } from 'url';

// Fix module load error by using explicit relative path
import { db } from './core/db.js';
import { config } from './config/index.js';
import { PATHS, PROJECT_ROOT as EngineProjectRoot } from './config/paths.js'; // MODELS_DIR removed — deprecated, no model-running features exist
import { apiKeyAuth } from './middleware/auth.js';
import { pathManager } from './utils/path-manager.js';
import { StructuredLogger } from './utils/structured-logger.js';

// ============================================================================
// OPS-005: Crash Observability (Standard 022) — ISSUE-17
// Install global guards before any route is served so a silent process death
// always leaves a stack trace in the rotating engine log AND stderr. WASM-originated
// aborts cannot be caught here, but every JS throw / unhandled rejection can.
// ============================================================================
function installCrashGuards(): void {
  const crashLogPath = path.join(PATHS.LOGS_DIR, 'anchor_engine_crash.log');
  const writeCrash = (kind: string, err: unknown) => {
    const stack = err instanceof Error ? (err.stack || `${err.name}: ${err.message}`) : String(err);
    const entry = `[${new Date().toISOString()}] [CRASH:${kind}] ${stack}\n`;
    try {
      if (!existsSync(PATHS.LOGS_DIR)) mkdirSync(PATHS.LOGS_DIR, { recursive: true });
      appendFileSync(crashLogPath, entry);
    } catch (logErr) {
      // Never let logging the crash itself throw — fall through to stderr.
      console.error(`[CRASH:${kind}] failed to write ${crashLogPath}:`, logErr);
    }
    console.error(entry);
  };

  const onUncaught = (err: unknown) => {
    writeCrash('uncaughtException', err);
    process.exit(1);
  };
  const onUnhandledRejection = (reason: unknown) => {
    writeCrash('unhandledRejection', reason);
    process.exit(1);
  };

  try {
    process.on('uncaughtException', onUncaught);
    process.on('unhandledRejection', onUnhandledRejection);
    console.log('[OPS-005] Crash observability guards installed (uncaughtException + unhandledRejection)');
  } catch (installErr) {
    // Guard installation failure at boot must be logged loudly before routes start.
    console.error('[OPS-005] FAILED to install crash guards:', installErr);
  }
}

installCrashGuards();

// Use a simpler approach for __dirname in ES modules
const getDirname = () => {
  try {
    return fileURLToPath(new URL('.', import.meta.url).pathname);
  } catch {
    // Fallback for environments where URL parsing fails
    return process.cwd();
  }
};

const __filename = path.join(getDirname(), 'index.js');
const __dirname = getDirname();

const app: express.Application = express();
const { PORT } = config;

// Use configured file size limit + 50% buffer for JSON overhead (base64/escaping)
const jsonLimit = Math.ceil((config.LIMITS?.MAX_FILE_SIZE_BYTES || 10 * 1024 * 1024) * 1.5);

app.use(cors());
app.use(express.json({ limit: jsonLimit }));
app.use(express.urlencoded({ extended: true }));

// HTTP Request Logging Middleware
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    const status = res.statusCode;

    // Skip logging for health checks and 304 (Not Modified) responses
    // Health checks poll every minute and create log spam
    if (status === 304 || req.path === '/health') {
      return;
    }

    StructuredLogger.info('HTTP_REQUEST', {
      method: req.method,
      path: req.path,
      status,
      duration_ms: duration,
    });

    // Mark activity for idle manager (skip static files)
    if (!req.path.startsWith('/static') && !req.path.startsWith('/chat')) {
      idleManager.markActive(`${req.method} ${req.path}`);
    }
  });
  next();
});

// Error handler with proper type handling

// Global state tracker
let databaseReady = false;

// Global 503 Guard for API routes
app.use('/v1', (req, res, next) => {
  if (!databaseReady) {
    return res.status(503).json({
      error: 'Service temporarily unavailable',
      message: 'Database initializing, please wait...',
    });
  }
  next();
});

// Security: Require API key to be configured (runs after auth middleware)
if (!config.API_KEY || config.API_KEY.length < 32) {
  console.error('\n❌ FATAL: API key not configured!');
  console.error('   Please set server.api_key in user_settings.json');
  console.error('   Requirements:');
  console.error('   - Length: 32-128 characters');
  console.error('   - Must contain at least one uppercase letter (A-Z), one lowercase (a-z), and one digit (0-9)');
  console.error('   - OR: 64+ character hex key (e.g., from crypto.randomBytes)');
  console.error('   Example: { "server": { "api_key": "MySecureKey123..." } }\n');
  process.exit(1);
}

// Validate API key strength (duplicate of Zod check - provides better error messages)
// Accepts: mixed case+digit (32-128 chars) OR 64+ char hex key
// Note: Zod schema enforces 32-128 length, runtime check adds length validation for hex keys
const api_key_strength = /^[A-Z]/.test(config.API_KEY) && /[a-z]/.test(config.API_KEY) && /\d/.test(config.API_KEY);
if (config.API_KEY.length < 64 && !api_key_strength) {
  console.error('\n❌ FATAL: API key is too weak!');
  console.error('   Your key does not meet the strength requirements:');
  console.error('   - Length: 32-128 characters with uppercase, lowercase, and digit');
  console.error('   - OR: 64+ character hex string (e.g., crypto.randomBytes(32).toString("hex"))');
  console.error('   Example: "MySecureKey123..." or hex key from crypto.randomBytes\n');
  process.exit(1);
}

StructuredLogger.info('AUTH_CONFIG', { api_key_enabled: true, key_length: config.API_KEY.length });

// Rate limiting — applied after auth so authenticated clients share the same window
// General limit: 100 requests / minute per IP
const apiLimiter = rateLimit({
  windowMs: 60_000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests', message: 'Rate limit exceeded. Try again in a minute.' },
});
// Stricter limit for expensive write operations: 20 / minute per IP
const ingestLimiter = rateLimit({
  windowMs: 60_000,
  max: 20,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Rate limit exceeded', message: 'Ingest rate limit exceeded. Try again in a minute.' },
});
app.use('/v1', apiLimiter);
app.use('/v1/memory/ingest', ingestLimiter);
app.use('/v1/watchdog/ingest', ingestLimiter);

// Set up static file serving immediately so UI is accessible
StructuredLogger.info('UI_SETUP', { static_path: '/static' });
app.use('/static', express.static(path.join(__dirname, '../dist'), {
  setHeaders: (res, path) => {
    // Only log debug-level for static files to avoid spam
    StructuredLogger.silly('STATIC_FILE', { path });
  },
}));

// Cache-busting middleware for HTML files (JS/CSS have content hashes)
function setUICacheHeaders(res: express.Response, filePath: string) {
  if (filePath.endsWith('.html')) {
    // NEVER cache HTML - always fetch fresh
    res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.set('Pragma', 'no-cache');
    res.set('Expires', '0');
  } else if (filePath.endsWith('.js') || filePath.endsWith('.css')) {
    // JS/CSS have content hashes - cache forever
    res.set('Cache-Control', 'public, max-age=31536000, immutable');
  }
}

// Serve UI with fallback chain:
// 1. Centralized dist (~/.anchor/dist) if built externally
// 2. engine/public (single-file React app)
// 3. integrations/web-dashboard/dist (development dashboard)
const centralizedDist = PATHS.DIST_DIR;
const internalFrontendDist = path.join(EngineProjectRoot, 'engine/public');
const externalFrontendDist = path.join(EngineProjectRoot, 'integrations/web-dashboard/dist');

if (existsSync(internalFrontendDist)) {
  StructuredLogger.info('UI_SOURCE', { source: 'internal', path: internalFrontendDist });
  app.use(express.static(internalFrontendDist, {
    setHeaders: (res, path) => {
      StructuredLogger.silly('UI_FILE_SERVED', { path, source: 'internal' });
      setUICacheHeaders(res, path);
    },
  }));
  app.get('*', (req, res, next) => {
    if (req.path.startsWith('/v1') || req.path.startsWith('/health') || req.path.startsWith('/monitoring')) return next();
    setUICacheHeaders(res, 'index.html');
    res.sendFile(path.join(internalFrontendDist, 'index.html'));
  });
} else if (existsSync(externalFrontendDist)) {
  StructuredLogger.info('UI_SOURCE', { source: 'external', path: externalFrontendDist });
  app.use(express.static(externalFrontendDist, {
    setHeaders: (res, path) => {
      StructuredLogger.silly('UI_FILE_SERVED', { path, source: 'external' });
      setUICacheHeaders(res, path);
    },
  }));
  app.get('*', (req, res, next) => {
    if (req.path.startsWith('/v1') || req.path.startsWith('/health') || req.path.startsWith('/monitoring')) return next();
    setUICacheHeaders(res, 'index.html');
    res.sendFile(path.join(externalFrontendDist, 'index.html'));
  });
} else {
  StructuredLogger.info('UI_SOURCE', { source: 'none', path: 'no UI found' });
}

// Add explicit /chat route logging
app.get('/chat', (req, res, next) => {
  StructuredLogger.info('CHAT_PAGE_REQUEST', { ip: req.ip });
  next();
});

// Set up a health route that works in both initialized and uninitialized states
app.get('/health', async (_req, res) => {
  if (!databaseReady) {
    return res.status(200).json({
      status: 'starting',
      timestamp: new Date().toISOString(),
      message: 'Engine is starting up, database not yet initialized',
    });
  }

  // When DB is ready, perform full health check
  try {
    // Test database connectivity
    const result = await db.run('SELECT 1 as test');
    if (result && result.rows && result.rows.length > 0) {
      res.status(200).json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        message: 'Anchor Context Engine is running and database is responsive',
      });
    } else {
      res.status(503).json({
        status: 'degraded',
        timestamp: new Date().toISOString(),
        message: 'Engine is running but database query returned unexpected results',
      });
    }
  } catch (dbError) {
    res.status(503).json({
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      message: 'Database is not responding properly',
      error: (dbError as Error).message,
    });
  }
});

// Set up API routes that can handle uninitialized state
// Use more specific patterns to avoid conflicts with health route


// Set up the catch-all route for UI (should be LAST)
// Catch-all moved to end of startServer to avoid intercepting dynamic routes


async function startServer() {
  const startupStartTime = Date.now();
  
  try {
    console.time('⏱️ Startup Time');
    console.log('Initializing Anchor Context Engine...');

    // Start the server immediately so health checks pass
    // V5.1 API Error Contract: Global error handler (returns JSON, not HTML)
    app.use((err: any, req: express.Request, res: express.Response, next: (err?: any) => void) => {
      const statusCode = err.statusCode || err.status || 500;
      res.status(statusCode).json({
        error: err.name || 'InternalError',
        message: err.message || 'An unexpected error occurred',
        ...(process.env.NODE_ENV !== 'production' && { stack: err.stack }),
      });
    });

    app.listen(PORT, config.HOST, () => {
      console.log(`Anchor Context Engine running on ${config.HOST}:${PORT}`);
      console.log(`Health check available at http://${config.HOST}:${PORT}/health`);
    });

    // Initialize database in the background after server starts
    console.log('Initializing database in the background...');
    await db.init();
    databaseReady = true;
    console.log('Database initialized successfully');

    // Cleanup blacklisted tags from database
    console.log('[Startup] Cleaning up blacklisted tags...');
    const { cleanupBlacklistedTags } = await import('./utils/tag-cleanup.js');
    await cleanupBlacklistedTags();



    console.log('Setting up full routes after database initialization...');

    // Now that DB is ready, import and set up full routes
    const { setupRoutes } = await import('./routes/api.js');
    const { setupHealthRoutes } = await import('./routes/health.js');
    const { monitoringRouter } = await import('./routes/monitoring.js');

    // Set up all API routes (delegates to v1 modules including system + settings)
    setupRoutes(app);

    // Set up full health routes (this will replace the basic one)
    setupHealthRoutes(app);

    // Set up monitoring routes
    app.use('/monitoring', monitoringRouter);

    // V5.1 API Error Contract: Catch-all for unmatched /v1 routes returns JSON (not HTML)
    // Must be placed AFTER all /v1 route handlers are registered
    app.use('/v1', (_req: express.Request, res: express.Response) => {
      res.status(404).json({ error: 'Not Found', message: `Cannot ${_req.method} ${_req.path}` });
    });

    console.log('Full routes set up, server is ready for all requests');
    console.timeEnd('⏱️ Startup Time');

    // Start other services after database is ready
    console.log('[Services] Starting child services via ProcessManager...');


    // P0 Critical Fix: Watchdog Auto-Enable (FRICTIONLESS_SPEC.md section 1.2)
    // Watchdog auto-start controlled by user_settings.json (watcher.auto_start)
    // Environment variable AUTO_START_WATCHDOG overrides settings file
    let watchdogEnabled = false;
    try {
        const { startWatchdog } = await import('./services/ingest/watchdog.js');

        // Check environment variable first (explicit user control)
        const envAutoStart = process.env.AUTO_START_WATCHDOG === 'true';
        
        // Fall back to settings file
        const settingsAutoStart = config.WATCHER?.AUTO_START === true;

        if (envAutoStart || settingsAutoStart) {
            console.log('[Services] Watchdog: auto-starting (AUTO_START_WATCHDOG=true or watcher.auto_start=true)...');
            await startWatchdog();
            console.log('[Services] ✅ Watchdog auto-started successfully');
            watchdogEnabled = true;
        } else {
            console.log('[Services] Watchdog: disabled (set AUTO_START_WATCHDOG=true or watcher.auto_start=true to enable)');
        }
    } catch (error: any) {
        console.warn('[Services] Watchdog auto-start failed:', error.message);
    }

    // Dreamer service disabled - optimized for STAR algorithm startup (VERSION)
    console.log('[Services] All service start commands queued');

    // ============================================
    // Standard 110: Regenerate Derived Data
    // ============================================
    // On startup: regenerate all derived data from inbox/ (source of truth)

    // 1. Create mirror from inbox/ files
    console.log('[Startup] Regenerating mirrored_brain/ from inbox/ (Standard 110)...');
    const { createMirror } = await import('./services/mirror/mirror.js');
    await createMirror();

    // 2. Generate synonym rings automatically (Standard 111)
    console.log('[Startup] Auto-generating synonym rings from data (Standard 111)...');
    try {
      const { AutoSynonymGenerator } = await import('./services/synonyms/auto-synonym-generator.js');
      const generator = new AutoSynonymGenerator();

      // Run synonym generation in background with timeout (don't block startup)
      console.log('[Startup] Starting synonym generation in background (may take several minutes)...');

      // Set timeout for synonym generation (5 minutes max)
      const SYNONYM_TIMEOUT = 5 * 60 * 1000; // 5 minutes

      const synonymPromise = Promise.race([
        generator.generateSynonymRings(),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Synonym generation timeout after 5 minutes')), SYNONYM_TIMEOUT),
        ),
      ]);

      synonymPromise.then(async synonyms => {
        // Save to auto-generated path (cleared on shutdown)
        const synonymPath = path.join(PATHS.FALLBACK_DATA_DIR, 'synonym-ring-auto.json');
        await generator.saveSynonymRings(synonyms, synonymPath);
        console.log(`[Startup] ✅ Synonym rings generated and saved to ${synonymPath}`);
      }).catch(error => {
        console.warn(`[Startup] ⚠️ Synonym generation failed or timed out: ${error.message}`);
        console.warn('[Startup] Will retry on next startup or run manually with: pnpm run generate-synonyms');
      });

      // Don't wait for synonym generation to complete - system is ready
      console.log('[Startup] System ready. Synonym generation running in background...');
    } catch (error: any) {
      console.warn('[Startup] Synonym generation failed:', error.message);
      console.warn('[Startup] Search will work without synonym expansion.');
    }

    console.log('[Startup] All derived data regenerated. System ready.');


    // ============================================
    // P0 Critical Fix: Display Startup Status Banner
    // FRICTIONLESS_SPEC.md section 1.3
    // ============================================
    const { displayStartupBanner } = await import('./utils/startup-banner.js');
    await displayStartupBanner({
      startupTimeMs: Date.now() - startupStartTime,
      watchdogEnabled,
    });

  } catch (error) {
    console.error('Failed to start Anchor Context Engine:', error);
    process.exit(1);
  }
}

// Windows graceful shutdown fix
process.on('SIGINT', async () => {
  // Safety net: force exit if cleanup hangs (e.g., db.close deadlock)
  const forceExitTimer = setTimeout(() => {
    console.error('[Shutdown] ⚠ Cleanup timed out after 10s — forcing exit');
    process.exit(1);
  }, 10_000);
  forceExitTimer.unref();

  try {
    console.log('[Shutdown] Starting graceful shutdown...');

    const { ProcessManager } = await import('./utils/process-manager.js');
    ProcessManager.getInstance().stopAll();

    // Close database connection first (releases file locks)
    console.log('[Shutdown] Closing database connection...');
    await db.close();

    // Standard 110: Ephemeral Index Architecture
    // Clear ALL derived data on shutdown - only inbox/ is source of truth
    // Controlled by user_settings.json (database.wipe_on_shutdown, watcher.wipe_mirrored_brain_on_shutdown)

    // 1. Wipe PGlite Database (index/cache) - controlled by database.wipe_on_shutdown
    const shouldWipeDb = config.DATABASE?.WIPE_ON_SHUTDOWN === true;
    if (shouldWipeDb) {
      const dbPath = process.env.PGLITE_DB_PATH || path.join(PATHS.FALLBACK_DATA_DIR, 'context', 'context.db');
      if (existsSync(dbPath)) {
        console.log('[Shutdown] Wiping PGlite database (database.wipe_on_shutdown=true)...');
        try {
          rmSync(dbPath, { recursive: true, force: true });
          console.log('[Shutdown] ✓ PGlite database wiped.');
        } catch (e: any) {
          console.warn(`[Shutdown] ⚠ Could not wipe PGlite database: ${e.message}`);
          console.warn('[Shutdown] Will be wiped on next startup');
        }
      }
    } else {
      console.log('[Shutdown] Skipping DB wipe (set database.wipe_on_shutdown=true to enable)');
    }

    // 2. Wipe SQLite3 context.db (anchor-core FFI database)
    const contextDbPath = path.join(PATHS.FALLBACK_DATA_DIR, 'context', 'context.db');
    if (existsSync(contextDbPath) && shouldWipeDb) {
      console.log('[Shutdown] Wiping SQLite3 context.db (anchor-core FFI)...');
      try {
        rmSync(contextDbPath, { force: true });
        console.log('[Shutdown] ✓ SQLite3 context.db wiped.');
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not wipe SQLite3 context.db: ${e.message}`);
        console.warn('[Shutdown] Will be wiped on next startup');
      }
    }

    // 3. Clear mirrored_brain/ (extracted from inbox/, regenerated on start)
    // Controlled by watcher.wipe_mirrored_brain_on_shutdown
    const shouldWipeMirror = config.WATCHER?.WIPE_MIRRORED_BRAIN_ON_SHUTDOWN === true;
    if (shouldWipeMirror) {
      const { MIRRORED_BRAIN_PATH } = await import('./services/mirror/mirror.js');
      if (existsSync(MIRRORED_BRAIN_PATH)) {
        console.log('[Shutdown] Clearing mirrored_brain/ (watcher.wipe_mirrored_brain_on_shutdown=true)...');
        try {
          rmSync(MIRRORED_BRAIN_PATH, { recursive: true, force: true });
          console.log('[Shutdown] ✓ mirrored_brain/ cleared.');
        } catch (e: any) {
          console.warn(`[Shutdown] ⚠ Could not clear mirrored_brain/: ${e.message}`);
        }
      }
    } else {
      console.log('[Shutdown] Skipping mirrored_brain wipe (set watcher.wipe_mirrored_brain_on_shutdown=true to enable)');
    }

    // 4. Clear GitHub Mirror Directory (cloned repos, derived from ingestion)
    const githubMirrorDir = path.join(PATHS.EXTERNAL_INBOX_DIR, 'github');
    if (existsSync(githubMirrorDir)) {
      console.log('[Shutdown] Clearing GitHub mirror directory...');
      try {
        rmSync(githubMirrorDir, { recursive: true, force: true });
        console.log('[Shutdown] ✓ GitHub mirror directory cleared.');
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not clear GitHub mirror: ${e.message}`);
      }
    }

    // 5. Clean up orphaned files in external-inbox (not under github/)
    const externalInboxDir = PATHS.EXTERNAL_INBOX_DIR;
    if (existsSync(externalInboxDir)) {
      const entries = readdirSync(externalInboxDir);
      for (const entry of entries) {
        const entryPath = path.join(externalInboxDir, entry);
        // Check if it's a directory by checking if it ends with /
        const stat = statSync(entryPath);
        if (stat.isDirectory()) {
          // Keep only the 'github' directory
          if (path.basename(entry) === 'github') {
            continue;
          }
          // Remove other directories
          console.log(`[Shutdown] Removing orphaned directory: ${entry}`);
          rmSync(entryPath, { recursive: true, force: true });
        } else {
          // Remove orphaned files
          console.log(`[Shutdown] Removing orphaned file: ${entry}`);
          rmSync(entryPath, { force: true });
        }
      }
      console.log('[Shutdown] ✓ Orphaned files in external-inbox cleaned.');
    }

    // 6. Clear Auto-Generated Synonym Rings (derived from data, regenerated on start)
    const synonymPath = path.join(PATHS.FALLBACK_DATA_DIR, 'notebook', 'synonym-ring-auto.json');
    if (existsSync(synonymPath)) {
      console.log('[Shutdown] Clearing auto-generated synonym rings...');
      try {
        rmSync(synonymPath, { force: true });
        console.log('[Shutdown] ✓ Synonym rings cleared.');
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not clear synonym rings: ${e.message}`);
      }
    }

    // 6. Clear Tag Audit Cache (derived from tags, regenerated on demand)
    const tagAuditPath = path.join(PATHS.FALLBACK_DATA_DIR, 'notebook', 'tag-audit-cache.json');
    if (existsSync(tagAuditPath)) {
      console.log('[Shutdown] Clearing tag audit cache...');
      try {
        rmSync(tagAuditPath, { force: true });
        console.log('[Shutdown] ✓ Tag audit cache cleared.');
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not clear tag audit cache: ${e.message}`);
      }
    }

    console.log('[Shutdown] ✓ Cleanup complete.');
    console.log('[Shutdown] Source of truth preserved: inbox/ + external-inbox/');
    console.log('[Shutdown] On restart: mirror + index + synonyms regenerated from inbox/');
    console.log('[Shutdown] GitHub mirror directory cleared to prevent duplicate repos');

    process.exit(0);
  } catch (e) {
    console.error('[Shutdown] Error during cleanup:', e);
    process.exit(1);
  }
});

// Memory warning event handler
import { resourceManager } from './utils/resource-manager.js';
process.on('warning', warning => {
  console.warn('Process warning:', warning.name, warning.message);
  if (warning.name.includes('Memory') || warning.message.includes('heap')) {
    console.log('Performing memory optimization due to warning...');
    resourceManager.optimizeMemory();
  }
});

// Initialize Idle Manager for automatic memory cleanup during inactivity
import { idleManager } from './services/idle-manager.js';
console.log('[IdleManager] Service initialized');

startServer();
export { app };