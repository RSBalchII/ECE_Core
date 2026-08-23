/**
 * Distillation Output Logger
 *
 * Writes distillation results to a single consolidated .log file per test run.
 * Truncates at 500 lines maximum.
 * Uses plain .log extension instead of YAML/JSON in filenames.
 */

import fs from 'fs';
import path from 'path';
import { PATHS } from '../../config/paths.js';

// Log directory for distillation outputs – uses ~/.anchor/logs (Standard 110).
// FIX (2026-08-21): was `path.join(PROJECT_ROOT, '.anchor')` with PROJECT_ROOT = cwd/../..,
// which wrote logs into the repo's <workspace>/.anchor instead of $HOME.
const ANCHOR_ROOT = PATHS.ANCHOR_ROOT;
const LOGS_DIR = path.join(ANCHOR_ROOT, 'logs');

/** Maximum number of lines we keep per unique output hash. */
const MAX_LINES_PER_FILE = 500;
/** Optional: maximum file size (MiB) before we start trimming aggressively. */
const MAX_LOG_FILE_SIZE_MB = 10;

// In‑memory cache mapping a query hash → { path, lastWrite }
const logFileCache = new Map<string, { path: string; lastWrite: number }>();

/** Ensure the log directory exists – idempotent. */
function ensureLogDir(): void {
  if (!fs.existsSync(LOGS_DIR)) fs.mkdirSync(LOGS_DIR, { recursive: true });
}

/** Check if distillation logging is enabled via environment variable. */
export function isDistillationLoggingEnabled(): boolean {
  const val = process.env.ANCHOR_DISTILL_LOG ?? '';
  return val === '1' || val.toLowerCase() === 'true';
}

/** Generate a deterministic hex‑string hash from the output path. */
export function generateOutputHash(outputPath: string): string {
  let h = 0;
  for (let i = 0; i < outputPath.length; i++) {
    h = ((h << 5) - h + outputPath.charCodeAt(i)) | 0;
  }
  return Math.abs(h).toString(16);
}

/** Entry format written into the JSON file (one per invocation). */
export interface DistillLogEntry {
  timestamp: string;          // ISO‑8601 UTC
  unixTimestamp: number;      // epoch ms – handy for debugging/logging
  outputHash: string;
  outputPath: string;         // full path to the YAML/JSON file
  outputFormat: 'yaml' | 'json-full' | 'decision-records';
  entrySize: number;          // bytes written
  decisionRecords: number;
  compressionRatio?: string;
  durationMs?: number;
}

/**
 * Persist a single distillation invocation.
 * The helper will append to a new consolidated .log file per test run.
 */
export function logDistillOutput(
  outputPath: string,
  outputFormat: 'yaml' | 'json-full' | 'decision-records',
  entrySize: number,
  metadata?: Partial<DistillLogEntry>,
  options?: { verbose?: boolean; force?: boolean }
): void {
  const enabled = (options?.verbose ?? false) || (options?.force ?? false);
  if (!enabled && !process.env.ANCHOR_DISTILL_LOG) return;

  ensureLogDir();
  const outputHash = generateOutputHash(outputPath);
  // Use current second for filename - same second = same test run
  const ts = new Date().toISOString().split('.')[0].replace(/[-:]/g, '');
  const fileName = `${ts}_distill.log`;
  const filePath = path.join(LOGS_DIR, fileName);

  // Format this entry as a single-line JSON object
  const entryLine = JSON.stringify({
    timestamp: new Date().toISOString(),
    unixTimestamp: Date.now(),
    outputHash,
    outputPath,
    outputFormat,
    entrySize,
    decisionRecords: metadata?.decisionRecords ?? 0,
    compressionRatio: metadata?.compressionRatio,
    durationMs: metadata?.durationMs,
  });

  // Read existing lines if file exists
  let existingLines: string[] = [];
  if (fs.existsSync(filePath)) {
    try {
      const raw = fs.readFileSync(filePath, 'utf-8');
      existingLines = raw.split('\n').filter(line => line.trim() !== '');
    } catch (_) {
      // corrupted – start fresh
      existingLines = [];
    }
  }

  // Check if we have deduplicated this output hash already in current file
  const hasDuplicate = existingLines.some(line => {
    try {
      const entry = JSON.parse(line);
      return entry.outputHash === outputHash && entry.outputPath === outputPath;
    } catch {
      return false;
    }
  });

  // If duplicate, skip writing to avoid bloat within same test run
  if (hasDuplicate) {
    return; // Already logged this hash in current file
  }

  // Append new line – but truncate at MAX_LINES_PER_FILE first
  const maxLines = MAX_LINES_PER_FILE;
  
  // Remove oldest lines to make room for new entry
  while (existingLines.length >= maxLines) {
    existingLines.shift(); // remove oldest line
  }

  // Add new line
  existingLines.push(entryLine);

  // Write back to file – compact format, one JSON object per line
  fs.writeFileSync(filePath, existingLines.join('\n'), 'utf-8');
}

/** Helper used by unit tests – returns all .log filenames in the log directory. */
export function listLogFiles(): string[] {
  ensureLogDir();
  return fs.readdirSync(LOGS_DIR).filter(f => f.endsWith('.log'));
}

/** Clear the in‑memory cache – useful for isolated test runs. */
export function clearCachedLogs(): void { logFileCache.clear(); }
