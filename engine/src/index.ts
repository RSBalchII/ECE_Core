
// engine/src/index.ts
import 'dotenv/config';
import express, { Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';

// Fix module load error by using explicit relative path or even require
import { db } from './core/db.js';

import { setupRoutes } from './routes/api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = parseInt(process.env['PORT'] || '3000', 10);

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));

setupRoutes(app);

app.use('/static', express.static(path.join(__dirname, '../dist')));

app.get('/health', (_req: Request, res: Response) => {
  res.status(200).json({
    status: 'Sovereign',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    version: '1.0.0'
  });
});

const FRONTEND_DIST = path.join(__dirname, '../../frontend/dist');
app.use(express.static(FRONTEND_DIST));

app.get('*', (_req, res) => {
  if (_req.path.startsWith('/v1') || _req.path.startsWith('/health')) {
    res.status(404).json({ error: 'Not Found' });
    return;
  }
  res.sendFile(path.join(FRONTEND_DIST, 'index.html'));
});

async function startServer() {
  try {
    console.log('Initializing Sovereign Context Engine...');
    await db.init();

    app.listen(PORT, () => {
      console.log(`Sovereign Context Engine running on port ${PORT}`);
      console.log(`Health check available at http://localhost:${PORT}/health`);
    });

    const { startWatchdog } = await import('./services/ingest/watchdog.js');
    startWatchdog();

    const { dream } = await import('./services/dreamer/dreamer.js');
    const { config } = await import('./config/index.js');
    try {
      await dream();
    } catch (e) { }

    setInterval(async () => {
      try { await dream(); } catch (e) { }
    }, config.DREAM_INTERVAL_MS);

  } catch (error) {
    console.error('Failed to start:', error);
    process.exit(1);
  }
}

// Windows graceful shutdown fix
process.on('SIGINT', async () => {
  try { await db.close(); process.exit(0); } catch (e) { process.exit(1); }
});

startServer();
export { app };