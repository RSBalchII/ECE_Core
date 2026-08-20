/**
 * Version Utility (v5.2.0+)
 * 
 * Centralized version management that reads from database with file fallback
 * Bidirectional sync ensures changes persist across restarts
 */

import { db } from '../core/db.js';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';

// Standard 110: Use .anchor/user_settings.json for centralized configuration
const PROJECT_ROOT = process.env.PROJECT_ROOT || process.cwd();
const ANCHOR_ROOT = path.join(PROJECT_ROOT, '.anchor');
const SETTINGS_PATH = path.join(ANCHOR_ROOT, 'user_settings.json');

export async function loadVersion(): Promise<string> {
  try {
    // Try database first (v5.2.0+)
    const dbResult = await db.run('SELECT value FROM app_settings WHERE key = $1', ['version']);
    if (dbResult.rows && dbResult.rows.length > 0) {
      console.log(`[Version] Loaded version ${dbResult.rows[0].value} from database`);
      return dbResult.rows[0].value;
    }

    // Try .anchor/user_settings.json first (Standard 110)
    if (fs.existsSync(SETTINGS_PATH)) {
      const settings = JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8'));
      const version = settings.server?.version || settings.anchorEngine?.version || '5.2.0';
      console.log(`[Version] Loaded version ${version} from ${SETTINGS_PATH}`);
      return version;
    }

    // Fallback to project root user_settings.json
    const projectSettingsPath = path.join(PROJECT_ROOT, 'user_settings.json');
    if (fs.existsSync(projectSettingsPath)) {
      const settings = JSON.parse(fs.readFileSync(projectSettingsPath, 'utf8'));
      const version = settings.server?.version || settings.anchorEngine?.version || '5.2.0';
      console.log(`[Version] Loaded version ${version} from ${projectSettingsPath}`);
      return version;
    }

    // Final fallback to hardcoded version
    console.log('[Version] Using default version 5.2.0');
    return '5.2.0';
  } catch (error: unknown) {
    const err = error instanceof Error ? error : new Error(String(error));
    console.warn('[Version] Error loading version:', err.message);
    return '5.2.0';
  }
}

let _version: string | undefined;

/** Get the current engine version (cached after first call) */
export async function getVersion(): Promise<string> {
  if (!_version) {
    try {
      const v = await loadVersion();
      _version = v || '5.2.0';
    } catch {
      _version = '5.2.0';
    }
  }
  return _version;
}

/** Set version in database and file (bidirectional sync - v5.2.0+) */
export async function setVersion(version: string): Promise<void> {
  try {
    // Update database first
    await db.run('INSERT INTO app_settings (key, value, type) VALUES ($1, $2, $3) ON CONFLICT (key) DO UPDATE SET value = $2', [version, version, 'string']);
    
    // Also update file for backward compatibility and restart persistence
    if (fs.existsSync(SETTINGS_PATH)) {
      const settings = JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8'));
      if (!settings.server) settings.server = {};
      settings.server.version = version;
      fs.writeFileSync(SETTINGS_PATH, JSON.stringify(settings, null, 2));
    } else if (fs.existsSync(path.join(PROJECT_ROOT, 'user_settings.json'))) {
      const projectSettingsPath = path.join(PROJECT_ROOT, 'user_settings.json');
      const settings = JSON.parse(fs.readFileSync(projectSettingsPath, 'utf8'));
      if (!settings.server) settings.server = {};
      settings.server.version = version;
      fs.writeFileSync(projectSettingsPath, JSON.stringify(settings, null, 2));
    }
    
    // Update cache
    _version = version;
  } catch (error: unknown) {
    const err = error instanceof Error ? error : new Error(String(error));
    console.warn('[Version] Failed to set version:', err.message);
  }
}

/** Initialize version and set environment variable for logger services */
export async function initVersion(): Promise<void> {
  const version = await loadVersion();

  // Set environment variable for use by search logger and other modules
  if (typeof process.env.ENGINE_VERSION === 'undefined') {
    process.env.ENGINE_VERSION = version;
    console.log(`[Version] Engine version set to ${version} in process.env.ENGINE_VERSION`);
  } else {
    console.log(`[Version] ENGINE_VERSION already set to ${process.env.ENGINE_VERSION}`);
  }
  
  _version = version;
}

// Initialize immediately when this module is loaded
initVersion().catch((err) => {
  // Log error but don't crash - version loading is not critical
  console.error('[Version] Failed to initialize version system:', err);
});

/** Export VERSION as a string (for compatibility with code that expects it).
 * Uses the cached _version set by initVersion() above — avoids returning a Promise. */
export const VERSION = (_version ?? '5.2.0');
