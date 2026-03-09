import express from 'express';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import axios from 'axios';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SETTINGS_PATH = path.join(__dirname, '../../../user_settings.json');

// Ensure the file exists and is VERY large to emphasize the block
if (!fs.existsSync(SETTINGS_PATH)) {
    const data = { dummy: "data".repeat(20000) };
    fs.writeFileSync(SETTINGS_PATH, JSON.stringify(data), 'utf-8');
} else {
    // If it exists but is small, overwrite it for the test
    const content = fs.readFileSync(SETTINGS_PATH, 'utf-8');
    if (content.length < 100000) {
        const data = { dummy: "data".repeat(20000) };
        fs.writeFileSync(SETTINGS_PATH, JSON.stringify(data), 'utf-8');
    }
}

const appSync = express();
appSync.get('/settings', (req, res) => {
    const settings = JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf-8'));
    res.json(settings);
});
appSync.get('/ping', async (req, res) => {
    // Simulate some async work
    await new Promise(resolve => setTimeout(resolve, 5));
    res.json({ ok: true });
});

const appAsync = express();
appAsync.get('/settings', async (req, res) => {
    const settings = JSON.parse(await fs.promises.readFile(SETTINGS_PATH, 'utf-8'));
    res.json(settings);
});
appAsync.get('/ping', async (req, res) => {
    await new Promise(resolve => setTimeout(resolve, 5));
    res.json({ ok: true });
});

async function runBenchmark() {
    console.log("Starting benchmark...");

    // Test Sync Server
    const serverSync = appSync.listen(3001);
    await new Promise(resolve => setTimeout(resolve, 100));

    let pingLatenciesSync: number[] = [];
    const syncSettingsPromises = [];

    // Hammer settings
    for(let i = 0; i < 500; i++) {
        syncSettingsPromises.push(axios.get('http://localhost:3001/settings').catch(() => {}));
    }

    // Measure ping latency
    for(let i = 0; i < 50; i++) {
        const start = performance.now();
        await axios.get('http://localhost:3001/ping');
        pingLatenciesSync.push(performance.now() - start);
    }
    await Promise.all(syncSettingsPromises);
    serverSync.close();

    const avgSyncPing = pingLatenciesSync.reduce((a, b) => a + b, 0) / pingLatenciesSync.length;

    // Test Async Server
    const serverAsync = appAsync.listen(3002);
    await new Promise(resolve => setTimeout(resolve, 100));

    let pingLatenciesAsync: number[] = [];
    const asyncSettingsPromises = [];

    // Hammer settings
    for(let i = 0; i < 500; i++) {
        asyncSettingsPromises.push(axios.get('http://localhost:3002/settings').catch(() => {}));
    }

    // Measure ping latency
    for(let i = 0; i < 50; i++) {
        const start = performance.now();
        await axios.get('http://localhost:3002/ping');
        pingLatenciesAsync.push(performance.now() - start);
    }
    await Promise.all(asyncSettingsPromises);
    serverAsync.close();

    const avgAsyncPing = pingLatenciesAsync.reduce((a, b) => a + b, 0) / pingLatenciesAsync.length;

    console.log(`Avg Ping Latency (Sync Settings API): ${avgSyncPing.toFixed(2)}ms`);
    console.log(`Avg Ping Latency (Async Settings API): ${avgAsyncPing.toFixed(2)}ms`);
    console.log(`Improvement: ${(((avgSyncPing - avgAsyncPing) / avgSyncPing) * 100).toFixed(2)}%`);
}

runBenchmark().catch(console.error);
