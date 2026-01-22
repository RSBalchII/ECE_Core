/**
 * Sovereign Context Engine - Main Entry Point
 * 
 * This is the primary entry point for the TypeScript-based Context Engine.
 * It orchestrates all the core services including database management,
 * context ingestion, search functionality, and API services.
 */

import 'dotenv/config';


import express, { Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';

// Import core services
import { db } from './core/db.js';
import { setupRoutes } from './routes/api.js';

// For __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = parseInt(process.env['PORT'] || '3000', 10);

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));

// API Routes
setupRoutes(app);

// Serve static files from the dist directory
app.use('/static', express.static(path.join(__dirname, '../dist')));

// Health check endpoint
app.get('/health', (_req: Request, res: Response) => {
  res.status(200).json({
    status: 'Sovereign',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    version: '1.0.0'
  });
});

// Root endpoint
// Serve Static Frontend
const FRONTEND_DIST = path.join(__dirname, '../../frontend/dist');
app.use(express.static(FRONTEND_DIST));

// Fallback for SPA routing
app.get('*', (_req, res) => {
  // Check if it's an API call first to avoid swallowing 404s for API
  if (_req.path.startsWith('/v1') || _req.path.startsWith('/health')) {
    res.status(404).json({ error: 'Not Found' });
    return;
  }
  res.sendFile(path.join(FRONTEND_DIST, 'index.html'));
});

// Initialize the database and start the server
async function startServer() {
  try {
    console.log('Initializing Sovereign Context Engine...');

    // Initialize the database
    await db.init();
    console.log('Database initialized successfully');

    // Start the server immediately (Standard: Localhost Load First)
    app.listen(PORT, () => {
      console.log(`Sovereign Context Engine running on port ${PORT}`);
      console.log(`Health check available at http://localhost:${PORT}/health`);
    });

    // Auto-Restore logic
    try {
      const { listBackups, restoreBackup } = await import('./services/backup/backup.js');
      const backups = await listBackups();
      if (backups.length > 0) {
        const latest = backups[0];
        console.log(`[Startup] Found backup: ${latest}. Attempting restore...`);
        await restoreBackup(latest);
        console.log(`[Startup] Restore complete.`);
      } else {
        console.log(`[Startup] No backups found. Starting fresh.`);
      }
    } catch (e: any) {
      console.error(`[Startup] Restore failed: ${e.message}. Continuing...`);
    }

    // Start Watchdog
    // Start Watchdog
    const { startWatchdog } = await import('./services/ingest/watchdog.js');
    startWatchdog();

    // Start Dreamer Service (Temporal Clustering)
    const { dream } = await import('./services/dreamer/dreamer.js');
    const { config } = await import('./config/index.js');

    console.log(`[Startup] Initializing Dreamer (Interval: ${config.DREAM_INTERVAL_MS}ms)...`);

    // Trigger immediately on startup (Standard 072)
    try {
      console.log('[Startup] Triggering immediate Dreamer cycle...');
      await dream();
    } catch (e: any) {
      console.error(`[Startup] Immediate Dreamer cycle failed: ${e.message}`);
    }

    setInterval(async () => {
      try {
        const result = await dream();
        if (result.status !== 'skipped' && result.analyzed && result.analyzed > 0) {
          console.log(`[Dreamer] Cycle Complete: Analyzed ${result.analyzed}, Updated ${result.updated}`);
        }
      } catch (e: any) {
        console.error(`[Dreamer] Cycle Failed: ${e.message}`);
      }
    }, config.DREAM_INTERVAL_MS);

    // Start the server (Moved to top)
  } catch (error) {
    console.error('Failed to start the Sovereign Context Engine:', error);
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('\nShutting down gracefully...');
  try {
    await db.close();
    console.log('Database connection closed.');
    process.exit(0);
  } catch (error) {
    console.error('Error during shutdown:', error);
    process.exit(1);
  }
});

// Start the server
startServer();

export { app };