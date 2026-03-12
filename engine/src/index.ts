// engine/src/index.ts
import express from "express";
import cors from "cors";
import rateLimit from "express-rate-limit";
import path from "path";
import { fileURLToPath } from "url";
import { existsSync, rmSync } from "fs";

// Fix module load error by using explicit relative path
import { db } from "./core/db.js";
import { config } from "./config/index.js";
import { MODELS_DIR, PROJECT_ROOT } from "./config/paths.js";
import { apiKeyAuth } from "./middleware/auth.js";
import { pathManager } from "./utils/path-manager.js";
import { StructuredLogger } from "./utils/structured-logger.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app: express.Application = express();
const PORT = config.PORT;

// Security Fix: Limit JSON body size to prevent DoS via large payloads
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
      duration_ms: duration
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

// SECURITY FIX #4: Require API key in production (fail closed, not open)
const isProduction = process.env.NODE_ENV === 'production';
if (isProduction && !config.API_KEY) {
  throw new Error(
    'SECURITY ERROR: API_KEY must be set in production! ' +
    'Set server.api_key in user_settings.json or ANCHOR_API_KEY environment variable. ' +
    'For safety, the server will not start without authentication in production mode.'
  );
}

// API Key Authentication for /v1 routes
app.use('/v1', apiKeyAuth);
if (config.API_KEY) {
  StructuredLogger.info('AUTH_CONFIG', { api_key_enabled: true });
} else {
  StructuredLogger.warn('AUTH_CONFIG', {
    api_key_enabled: false,
    warning: '⚠️ NO API KEY CONFIGURED - Authentication disabled! DEVELOPMENT MODE ONLY. Set server.api_key in user_settings.json for production.'
  });
}

// Rate limiting — applied after auth so authenticated clients share the same window
// General limit: 100 requests / minute per IP
const apiLimiter = rateLimit({
  windowMs: 60_000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests', message: 'Rate limit exceeded. Try again in a minute.' }
});
// Stricter limit for expensive write operations: 20 / minute per IP
const ingestLimiter = rateLimit({
  windowMs: 60_000,
  max: 20,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Rate limit exceeded', message: 'Ingest rate limit exceeded. Try again in a minute.' }
});
app.use('/v1', apiLimiter);
app.use('/v1/memory/ingest', ingestLimiter);
app.use('/v1/watchdog/ingest', ingestLimiter);

// Set up static file serving immediately so UI is accessible
StructuredLogger.info('UI_SETUP', { static_path: '/static' });
app.use("/static", express.static(path.join(__dirname, "../dist"), {
  setHeaders: (res, path) => {
    // Only log debug-level for static files to avoid spam
    StructuredLogger.silly('STATIC_FILE', { path });
  }
}));

// Serve UI from engine/public (simplified single-file UI)
// Fallback to external anchor-os UI if running in full system mode
const internalFrontendDist = path.join(__dirname, "../public");
const externalFrontendDist = path.join(__dirname, "../../../anchor-os/packages/anchor-ui/dist");

if (existsSync(externalFrontendDist)) {
  StructuredLogger.info('UI_SOURCE', { source: 'external', path: externalFrontendDist });
  app.use(express.static(externalFrontendDist, {
    setHeaders: (res, path) => {
      StructuredLogger.silly('UI_FILE_SERVED', { path, source: 'external' });
    }
  }));
  app.get("*", (req, res, next) => {
    if (req.path.startsWith("/v1") || req.path.startsWith("/health") || req.path.startsWith("/monitoring")) return next();
    res.sendFile(path.join(externalFrontendDist, "index.html"));
  });
} else {
  StructuredLogger.info('UI_SOURCE', { source: 'internal', path: internalFrontendDist });
  app.use(express.static(internalFrontendDist, {
    setHeaders: (res, path) => {
      StructuredLogger.silly('UI_FILE_SERVED', { path, source: 'internal' });
    }
  }));
  app.get("*", (req, res, next) => {
    if (req.path.startsWith("/v1") || req.path.startsWith("/health") || req.path.startsWith("/monitoring")) return next();
    res.sendFile(path.join(internalFrontendDist, "index.html"));
  });
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
      status: "starting",
      timestamp: new Date().toISOString(),
      message: "Engine is starting up, database not yet initialized"
    });
  }

  // When DB is ready, perform full health check
  try {
    // Test database connectivity
    const result = await db.run('SELECT 1 as test');
    if (result && result.rows && result.rows.length > 0) {
      res.status(200).json({
        status: "healthy",
        timestamp: new Date().toISOString(),
        message: "Anchor Context Engine is running and database is responsive"
      });
    } else {
      res.status(503).json({
        status: "degraded",
        timestamp: new Date().toISOString(),
        message: "Engine is running but database query returned unexpected results"
      });
    }
  } catch (dbError) {
    res.status(503).json({
      status: "unhealthy",
      timestamp: new Date().toISOString(),
      message: "Database is not responding properly",
      error: (dbError as Error).message
    });
  }
});

// Set up API routes that can handle uninitialized state
// Use more specific patterns to avoid conflicts with health route

// Model Listing Endpoint (for UI)
app.get('/v1/models', (req, res) => {
  try {
    // Use the robust path from configuration (imported statically)
    let modelPath = config.LLM_MODEL_DIR || MODELS_DIR;

    // If config has a relative path, resolve it against project root
    if (config.LLM_MODEL_DIR && !path.isAbsolute(config.LLM_MODEL_DIR)) {
      // If it starts with ./models, it might be relative to project root
      // MODELS_DIR is already absolute path to project_root/models
      if (config.LLM_MODEL_DIR === './models' || config.LLM_MODEL_DIR === 'models') {
        modelPath = MODELS_DIR;
      } else {
        modelPath = path.resolve(PROJECT_ROOT, config.LLM_MODEL_DIR);
      }
    }

    if (!existsSync(modelPath)) {
      return res.json({ object: 'list', data: [] });
    }

    // Read directory
    import('fs').then(fsModule => {
      const files = fsModule.readdirSync(modelPath).filter(file => file.endsWith('.gguf'));
      const models = files.map(file => ({
        id: file,
        object: 'model',
        created: Math.floor(Date.now() / 1000),
        owned_by: 'anchor-os'
      }));
      res.json({ object: 'list', data: models });
    });
  } catch (error) {
    console.error('[Engine] Error listing models:', error);
    res.status(500).json({ error: (error as Error).message });
  }
});



// Set up the catch-all route for UI (should be LAST)
// Catch-all moved to end of startServer to avoid intercepting dynamic routes


async function startServer() {
  try {
    console.time("⏱️ Startup Time");
    console.log("Initializing Anchor Context Engine...");

    // ============================================
    // CRITICAL: Initialize database BEFORE server starts
    // This prevents race condition where requests hit uninitialized DB
    // ============================================
    console.log("Initializing database...");
    await db.init();
    databaseReady = true;
    console.log("Database initialized successfully");

    // Start the server AFTER database is ready
    app.listen(PORT, config.HOST, () => {
      console.log(`Anchor Context Engine running on ${config.HOST}:${PORT}`);
      console.log(`Health check available at http://${config.HOST}:${PORT}/health`);
    });

    // Cleanup blacklisted tags from database
    console.log('[Startup] Cleaning up blacklisted tags...');
    const { cleanupBlacklistedTags } = await import('./utils/tag-cleanup.js');
    await cleanupBlacklistedTags();

    // Initialize Vector Service
    const { vector } = await import("./core/vector.js");
    await vector.init();


    console.log("Setting up full routes after database initialization...");

    // Now that DB is ready, import and set up full routes
    const { setupRoutes } = await import("./routes/api.js");
    const { setupHealthRoutes } = await import("./routes/health.js");
    const { monitoringRouter } = await import("./routes/monitoring.js");

    // Set up all API routes (delegates to v1 modules including system + settings)
    setupRoutes(app);

    // Set up full health routes (this will replace the basic one)
    setupHealthRoutes(app);

    // Set up monitoring routes
    app.use('/monitoring', monitoringRouter);

    console.log("Full routes set up, server is ready for all requests");
    console.timeEnd("⏱️ Startup Time");

    // Start other services after database is ready
    console.log('[Services] Starting child services via ProcessManager...');

    // Note: Nanobot is now started by the unified launcher (start.bat/start.sh)
    // to prevent duplicate instances. ProcessManager is disabled for nanobot.
    console.log('[Services] Nanobot skipped (started by launcher)');

    // Watchdog is now controlled via UI settings - not auto-started
    console.log('[Services] Watchdog disabled - start from /settings UI');

    // Dreamer service disabled - optimized for STAR algorithm startup (v4.0)
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
          setTimeout(() => reject(new Error('Synonym generation timeout after 5 minutes')), SYNONYM_TIMEOUT)
        )
      ]);

      // FIX: Proper error handling - catch errors in .then() callback too
      synonymPromise.then(async (synonyms) => {
        // Save to auto-generated path (cleared on shutdown)
        const synonymPath = path.join(pathManager.getNotebookDir(), 'synonym-ring-auto.json');
        await generator.saveSynonymRings(synonyms, synonymPath);
        console.log(`[Startup] ✅ Synonym rings generated and saved to ${synonymPath}`);
      }).catch((error) => {
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


  } catch (error) {
    console.error("Failed to start Anchor Context Engine:", error);
    process.exit(1);
  }
}

// Windows graceful shutdown fix
process.on("SIGINT", async () => {
  // Safety net: force exit if cleanup hangs (e.g., db.close deadlock)
  const forceExitTimer = setTimeout(() => {
    console.error('[Shutdown] ⚠ Cleanup timed out after 10s — forcing exit');
    process.exit(1);
  }, 10_000);
  forceExitTimer.unref();

  try {
    console.log(`[Shutdown] Starting graceful shutdown...`);

    const { ProcessManager } = await import("./utils/process-manager.js");
    ProcessManager.getInstance().stopAll();

    // Close database connection first (releases file locks)
    console.log(`[Shutdown] Closing database connection...`);
    await db.close();

    // Standard 110: Ephemeral Index Architecture
    // Clear ALL derived data on shutdown - only inbox/ is source of truth

    // 1. Wipe PGlite Database (index/cache)
    const dbPath = process.env.PGLITE_DB_PATH || pathManager.getDatabasePath();
    if (existsSync(dbPath)) {
      console.log(`[Shutdown] Wiping PGlite database (rebuildable index)...`);
      try {
        rmSync(dbPath, { recursive: true, force: true });
        console.log(`[Shutdown] ✓ PGlite database wiped.`);
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not wipe PGlite database: ${e.message}`);
        console.warn(`[Shutdown] Will be wiped on next startup`);
      }
    }

    // 2. Wipe SQLite3 context.db (anchor-core FFI database)
    const contextDbPath = path.join(pathManager.getDatabaseDir(), 'context.db');
    if (existsSync(contextDbPath)) {
      console.log(`[Shutdown] Wiping SQLite3 context.db (anchor-core FFI)...`);
      try {
        rmSync(contextDbPath, { force: true });
        console.log(`[Shutdown] ✓ SQLite3 context.db wiped.`);
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not wipe SQLite3 context.db: ${e.message}`);
        console.warn(`[Shutdown] Will be wiped on next startup`);
      }
    }

    // 3. Clear mirrored_brain/ (extracted from inbox/, regenerated on start)
    const { MIRRORED_BRAIN_PATH } = await import('./services/mirror/mirror.js');
    if (existsSync(MIRRORED_BRAIN_PATH)) {
      console.log(`[Shutdown] Clearing mirrored_brain/ (regenerated from inbox/ on start)...`);
      try {
        rmSync(MIRRORED_BRAIN_PATH, { recursive: true, force: true });
        console.log(`[Shutdown] ✓ mirrored_brain/ cleared.`);
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not clear mirrored_brain/: ${e.message}`);
      }
    }

    // 4. Clear Auto-Generated Synonym Rings (derived from data, regenerated on start)
    const synonymPath = path.join(pathManager.getNotebookDir(), 'synonym-ring-auto.json');
    if (existsSync(synonymPath)) {
      console.log(`[Shutdown] Clearing auto-generated synonym rings...`);
      try {
        rmSync(synonymPath, { force: true });
        console.log(`[Shutdown] ✓ Synonym rings cleared.`);
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not clear synonym rings: ${e.message}`);
      }
    }

    // 5. Clear Tag Audit Cache (derived from tags, regenerated on demand)
    const tagAuditPath = path.join(pathManager.getNotebookDir(), 'tag-audit-cache.json');
    if (existsSync(tagAuditPath)) {
      console.log(`[Shutdown] Clearing tag audit cache...`);
      try {
        rmSync(tagAuditPath, { force: true });
        console.log(`[Shutdown] ✓ Tag audit cache cleared.`);
      } catch (e: any) {
        console.warn(`[Shutdown] ⚠ Could not clear tag audit cache: ${e.message}`);
      }
    }

    console.log(`[Shutdown] ✓ Cleanup complete.`);
    console.log(`[Shutdown] Source of truth preserved: inbox/ + external-inbox/`);
    console.log(`[Shutdown] On restart: mirror + index + synonyms regenerated from inbox/`);

    process.exit(0);
  } catch (e) {
    console.error('[Shutdown] Error during cleanup:', e);
    process.exit(1);
  }
});

// Memory warning event handler
import { resourceManager } from './utils/resource-manager.js';
process.on('warning', (warning) => {
  console.warn('Process warning:', warning.name, warning.message);
  if (warning.name.includes('Memory') || warning.message.includes('heap')) {
    console.log('Performing memory optimization due to warning...');
    resourceManager.optimizeMemory();
  }
});

// FIX: Global unhandled rejection handler to prevent crashes
process.on('unhandledRejection', (reason, promise) => {
  console.error('[UNHANDLED REJECTION] Promise:', promise);
  console.error('[UNHANDLED REJECTION] Reason:', reason);
  // Don't exit - log and continue (Node.js default is to crash)
});

// FIX: Global uncaught exception handler
process.on('uncaughtException', (error) => {
  console.error('[UNCAUGHT EXCEPTION]', error);
  // Attempt graceful shutdown
  process.exit(1);
});

// Initialize Idle Manager for automatic memory cleanup during inactivity
import { idleManager } from './services/idle-manager.js';
console.log('[IdleManager] Service initialized');

startServer();
export { app };