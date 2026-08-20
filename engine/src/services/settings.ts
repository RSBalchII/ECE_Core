/**
 * Settings Service — Database-Backed Configuration (v5.2.0+)
 * 
 * Priority chain: Function params → DB → env vars → file defaults
 * Bidirectional sync: API writes update both DB and user_settings.json
 */

import { db } from '../core/db.js';
import * as fs from 'fs/promises';
import * as path from 'path';
import { PATHS } from '../config/paths.js';

// Settings table schema (created on first startup)
const SETTINGS_TABLE = `
  CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    type TEXT DEFAULT 'string',
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )
`;

// Index for fast lookups by key prefix
const SETTINGS_INDEX = `CREATE INDEX IF NOT EXISTS idx_app_settings_key ON app_settings(key)`;

interface SettingRow {
  key: string;
  value: string;
  type: string;
  description?: string;
  updated_at: Date;
}

/**
 * Initialize settings table and import from file if needed
 */
export async function initSettings(): Promise<void> {
  try {
    await db.run(SETTINGS_TABLE);
    await db.run(SETTINGS_INDEX);
    
    // Import from user_settings.json on first startup (if DB is empty)
    const countResult = await db.run('SELECT COUNT(*) as cnt FROM app_settings');
    if (countResult.rows[0].cnt === 0) {
      console.log('[Settings] Importing settings from user_settings.json to database...');
      await importFromFile();
    } else {
      console.log('[Settings] Database already populated, skipping file import.');
    }
  } catch (error: any) {
    console.warn('[Settings] Failed to initialize settings table:', error.message);
    // Non-fatal — engine can still run with file-based config as fallback
  }
}

/**
 * Import all settings from user_settings.json into database
 */
async function importFromFile(): Promise<void> {
  try {
    const filePath = PATHS.USER_SETTINGS;
    if (!await fs.access(filePath).catch(() => false)) {
      console.log('[Settings] No user_settings.json found, skipping import.');
      return;
    }

    const content = await fs.readFile(filePath, 'utf-8');
    const settings = JSON.parse(content);
    
    // Flatten nested object to key-value pairs (e.g., "server.api_key" → value)
    const flatSettings = flattenObject(settings);
    
    for (const [key, value] of Object.entries(flatSettings)) {
      if (value !== undefined && value !== null) {
        await upsertSetting(key, String(value), typeof value === 'number' ? 'number' : 'string');
      }
    }
    
    console.log(`[Settings] Imported ${Object.keys(flatSettings).length} settings from file.`);
  } catch (error: any) {
    console.warn('[Settings] Failed to import from file:', error.message);
  }
}

/**
 * Get a setting value by key with priority chain resolution
 */
export async function getSetting(key: string, defaultValue?: any): Promise<any> {
  try {
    // 1. Try database first (v5.2.0+)
    const result = await db.run(
      'SELECT value FROM app_settings WHERE key = $1',
      [key]
    );
    
    if (result.rows.length > 0) {
      return coerceValue(result.rows[0].value, result.rows[0].type);
    }
    
    // 2. Fallback to environment variable
    const envKey = key.toUpperCase().replace(/\./g, '_');
    const envValue = process.env[`ANCHOR_${envKey}`];
    if (envValue !== undefined) {
      return coerceValue(envValue, 'string');
    }
    
    // 3. Fallback to file-based config
    try {
      const filePath = PATHS.USER_SETTINGS;
      if (await fs.access(filePath).catch(() => false)) {
        const content = await fs.readFile(filePath, 'utf-8');
        const settings = JSON.parse(content);
        const value = getNestedValue(settings, key);
        if (value !== undefined) {
          return coerceValue(String(value), typeof value === 'number' ? 'number' : 'string');
        }
      }
    } catch {
      // File read failed — continue to default
    }
    
    // 4. Return default
    return defaultValue;
  } catch (error: any) {
    console.warn(`[Settings] Failed to get setting "${key}":`, error.message);
    return defaultValue;
  }
}

/**
 * Set a setting value — updates both database and file
 */
export async function setSetting(key: string, value: any): Promise<void> {
  const stringValue = String(value);
  const type = typeof value === 'number' ? 'number' : 'string';
  
  try {
    // Validate before setting
    const validation = validateSetting(key, value);
    if (!validation.valid) {
      throw new Error(`Validation failed: ${validation.error}`);
    }

    // Log audit trail before update
    await logAuditEvent('SET', key, value, type);
    
    // 1. Update database (primary)
    await upsertSetting(key, stringValue, type);
    
    // 2. Sync to file (for persistence across restarts) — synchronous write-back
    // Awaiting ensures serialization when multiple keys are set in quick succession
    await syncToFile(key, value);
    
    console.log(`[Settings] Updated "${key}" = ${stringValue}`);
  } catch (error: any) {
    console.error(`[Settings] Failed to set "${key}":`, error.message);
    throw error;
  }
}

/**
 * Audit event log for tracking setting changes
 */
interface AuditEvent {
  timestamp: Date;
  action: 'SET' | 'DELETE' | 'IMPORT';
  key: string;
  oldValue?: any;
  newValue?: any;
  type?: string;
}

const AUDIT_LOG: AuditEvent[] = [];
const MAX_AUDIT_ENTRIES = 1000; // Keep last 1000 entries in memory

/**
 * Log an audit event for setting changes
 */
async function logAuditEvent(action: 'SET' | 'DELETE' | 'IMPORT', key: string, newValue?: any, type?: string): Promise<void> {
  try {
    // Get old value if available
    let oldValue: any;
    if (action === 'SET') {
      const result = await db.run('SELECT value, type FROM app_settings WHERE key = $1', [key]);
      if (result.rows.length > 0) {
        oldValue = coerceValue(result.rows[0].value, result.rows[0].type);
      }
    }

    const event: AuditEvent = {
      timestamp: new Date(),
      action,
      key,
      oldValue,
      newValue,
      type,
    };

    // Add to in-memory audit log (circular buffer)
    AUDIT_LOG.push(event);
    if (AUDIT_LOG.length > MAX_AUDIT_ENTRIES) {
      AUDIT_LOG.shift(); // Remove oldest entry
    }

    console.log(`[Audit] ${action} "${key}"`, oldValue !== undefined ? `from=${oldValue}` : '', newValue !== undefined ? `to=${newValue}` : '');
  } catch (error: any) {
    console.warn('[Audit] Failed to log event:', error.message);
  }
}

/**
 * Get audit trail for a specific setting key
 */
export async function getAuditTrail(key?: string): Promise<AuditEvent[]> {
  if (key) {
    return AUDIT_LOG.filter(event => event.key === key);
  }
  return [...AUDIT_LOG]; // Return copy
}

/**
 * Clear audit trail
 */
export async function clearAuditTrail(): Promise<void> {
  AUDIT_LOG.length = 0;
}

/**
 * Upsert a single setting row in database
 */
async function upsertSetting(key: string, value: string, type: string): Promise<void> {
  await db.run(
    `INSERT INTO app_settings (key, value, type, updated_at) 
     VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
     ON CONFLICT (key) DO UPDATE SET value = $2, type = $3, updated_at = CURRENT_TIMESTAMP`,
    [key, value, type]
  );
}

// Async write queue for user_settings.json — processes items one at a time
let settingsWriteQueue: Array<{ key: string; value: any; resolve: () => void; reject: (err: Error) => void }> = [];
let processingWrites = false;

/**
 * Sync a setting change to user_settings.json file (atomic, queued)
 * Each call adds itself to the queue and waits for its turn — no interleaving possible.
 */
async function syncToFile(key: string, value: any): Promise<void> {
  const filePath = PATHS.USER_SETTINGS;
  
  return new Promise<void>((resolve, reject) => {
    // Add this write to the queue
    settingsWriteQueue.push({ key, value, resolve, reject });
    
    // If no writer is active, start processing
    if (!processingWrites) {
      processWriteQueue(filePath);
    }
  });
}

async function processWriteQueue(filePath: string): Promise<void> {
  processingWrites = true;
  
  while (settingsWriteQueue.length > 0) {
    // Dequeue one item at a time — ensures no interleaving
    const { key, value, resolve, reject } = settingsWriteQueue.shift()!;
    
    try {
      let settings: Record<string, any> = {};
      
      if (await fs.access(filePath).catch(() => false)) {
        try {
          settings = JSON.parse(await fs.readFile(filePath, 'utf-8'));
        } catch {
          console.warn('[Settings] Corrupted user_settings.json detected, starting fresh');
          settings = {};
        }
      }
      
      setNestedValue(settings, key, value);
      
      const tmpPath = filePath + '.tmp';
      await fs.writeFile(tmpPath, JSON.stringify(settings, null, 2), 'utf-8');
      await fs.rename(tmpPath, filePath);
      
      resolve();
    } catch (err: any) {
      reject(err);
    }
  }
  
  processingWrites = false;
}

/**
 * Get all settings as a flat object
 */
export async function getAllSettings(): Promise<Record<string, any>> {
  try {
    const result = await db.run('SELECT key, value, type FROM app_settings');
    const settings: Record<string, any> = {};
    
    for (const row of result.rows) {
      settings[row.key] = coerceValue(row.value, row.type);
    }
    
    return settings;
  } catch (error: any) {
    console.warn('[Settings] Failed to get all settings:', error.message);
    return {};
  }
}

/**
 * Get settings by key prefix (e.g., "server." returns all server.* keys)
 */
export async function getSettingsByPrefix(prefix: string): Promise<Record<string, any>> {
  try {
    const result = await db.run(
      'SELECT key, value, type FROM app_settings WHERE key LIKE $1',
      [`${prefix}%`]
    );
    
    const settings: Record<string, any> = {};
    for (const row of result.rows) {
      settings[row.key] = coerceValue(row.value, row.type);
    }
    
    return settings;
  } catch (error: any) {
    console.warn(`[Settings] Failed to get settings with prefix "${prefix}":`, error.message);
    return {};
  }
}

/**
 * Delete a setting from both database and file
 */
export async function deleteSetting(key: string): Promise<void> {
  try {
    // Remove from database
    await db.run('DELETE FROM app_settings WHERE key = $1', [key]);
    
    // Remove from file
    const filePath = PATHS.USER_SETTINGS;
    if (await fs.access(filePath).catch(() => false)) {
      const content = await fs.readFile(filePath, 'utf-8');
      const settings = JSON.parse(content);
      deleteNestedValue(settings, key);
      await fs.writeFile(filePath, JSON.stringify(settings, null, 2), 'utf-8');
    }
    
    console.log(`[Settings] Deleted "${key}"`);
  } catch (error: any) {
    console.error(`[Settings] Failed to delete "${key}":`, error.message);
    throw error;
  }
}

// === Helper Functions ===

/**
 * Flatten nested object to dot-notation keys
 */
function flattenObject(obj: Record<string, any>, prefix = ''): Record<string, any> {
  const result: Record<string, any> = {};
  
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      // Recursively flatten nested objects
      Object.assign(result, flattenObject(value, fullKey));
    } else {
      result[fullKey] = value;
    }
  }
  
  return result;
}

/**
 * Get nested value from object using dot notation (e.g., "server.api_key")
 */
function getNestedValue(obj: Record<string, any>, key: string): any {
  const parts = key.split('.');
  let current = obj;
  
  for (const part of parts) {
    if (current === undefined || current === null) return undefined;
    current = current[part];
  }
  
  return current;
}

/**
 * Set nested value in object using dot notation
 */
function setNestedValue(obj: Record<string, any>, key: string, value: any): void {
  const parts = key.split('.');
  let current = obj;
  
  for (let i = 0; i < parts.length - 1; i++) {
    if (!(parts[i] in current) || typeof current[parts[i]] !== 'object') {
      current[parts[i]] = {};
    }
    current = current[parts[i]];
  }
  
  current[parts[parts.length - 1]] = value;
}

/**
 * Delete nested value from object using dot notation
 */
function deleteNestedValue(obj: Record<string, any>, key: string): void {
  const parts = key.split('.');
  let current = obj;
  
  for (let i = 0; i < parts.length - 1; i++) {
    if (!(parts[i] in current)) return;
    current = current[parts[i]];
  }
  
  delete current[parts[parts.length - 1]];
}

/**
 * Coerce string value to appropriate type based on setting type
 */
function coerceValue(value: string, type: string): any {
  switch (type) {
    case 'number':
      return Number(value);
    case 'boolean':
      return value === 'true';
    default:
      return value;
  }
}

// === Settings Validation & Schema Definition (v5.2.0+) ===

export interface SettingSchema {
  key: string;
  type: 'string' | 'number' | 'boolean';
  description: string;
  defaultValue?: any;
  validate?: (value: any) => boolean;
}

// Schema definition for all known settings
const SETTINGS_SCHEMA: Record<string, SettingSchema> = {
  // Server settings
  'server.host': { key: 'server.host', type: 'string', description: 'Server bind address' },
  'server.port': { key: 'server.port', type: 'number', defaultValue: 3160, validate: (v) => v >= 1 && v <= 65535, description: 'Server port number' },
  'server.api_key': { key: 'server.api_key', type: 'string', description: 'API authentication key' },

  // Database settings
  'database.wipe_on_startup': { key: 'database.wipe_on_startup', type: 'boolean', defaultValue: true, description: 'Wipe PGlite index on restart (Standard 051)' },

  // Tagging settings
  'tagging.modulation_level': { key: 'tagging.modulation_level', type: 'number', defaultValue: 50, validate: (v) => v >= 0 && v <= 100, description: 'Tag modulation level' },
  'tagging.atom_as_tag': { key: 'tagging.atom_as_tag', type: 'boolean', defaultValue: false, description: 'Use atoms as tags' },
  'tagging.strict_atom_selection': { key: 'tagging.strict_atom_selection', type: 'boolean', defaultValue: true, description: 'Strict atom selection mode' },

  // Search settings
  'search.strategy': { key: 'search.strategy', type: 'string', defaultValue: 'hybrid', description: 'Search strategy (hybrid/fts/vector)' },
  'search.max_chars_default': { key: 'search.max_chars_default', type: 'number', defaultValue: 524288, validate: (v) => v > 0, description: 'Default max characters for search' },
  'search.max_chars_limit': { key: 'search.max_chars_limit', type: 'number', defaultValue: 2000000, validate: (v) => v > 0, description: 'Absolute max characters limit' },

  // Memory/throttle settings
  'memory.heap_pressure_mb': { key: 'memory.heap_pressure_mb', type: 'number', defaultValue: 500, validate: (v) => v >= 0, description: 'Heap pressure threshold in MB' },
  'memory.throttle_start_mb': { key: 'memory.throttle_start_mb', type: 'number', defaultValue: 800, validate: (v) => v > 0, description: 'Throttle start threshold in MB' },
  'memory.throttle_max_mb': { key: 'memory.throttle_max_mb', type: 'number', defaultValue: 1200, validate: (v) => v > 0, description: 'Throttle max threshold in MB' },
  'memory.emergency_stop_mb': { key: 'memory.emergency_stop_mb', type: 'number', defaultValue: 1500, validate: (v) => v > 0, description: 'Emergency stop threshold in MB' },

  // Search performance settings
  'search.results_batch_size': { key: 'search.results_batch_size', type: 'number', defaultValue: 20, validate: (v) => v > 0, description: 'Batch size for search results' },
  'search.enable_streaming': { key: 'search.enable_streaming', type: 'boolean', defaultValue: false, description: 'Enable streaming search results' },

  // Context settings
  'context.relevance_weight': { key: 'context.relevance_weight', type: 'number', defaultValue: 0.7, validate: (v) => v >= 0 && v <= 1, description: 'Relevance weight in scoring' },
  'context.recency_weight': { key: 'context.recency_weight', type: 'number', defaultValue: 0.3, validate: (v) => v >= 0 && v <= 1, description: 'Recency weight in scoring' },

  // Physics settings
  'physics.damping_factor': { key: 'physics.damping_factor', type: 'number', defaultValue: 0.85, validate: (v) => v > 0 && v < 1, description: 'Physics damping factor' },
  'physics.time_decay_lambda': { key: 'physics.time_decay_lambda', type: 'number', defaultValue: 0.00001, validate: (v) => v >= 0, description: 'Time decay constant' },
  'physics.temperature': { key: 'physics.temperature', type: 'number', defaultValue: 0.2, validate: (v) => v >= 0 && v <= 1, description: 'Physics temperature parameter' },

  // Adaptive concurrency settings
  'adaptive_concurrency.environment': { key: 'adaptive_concurrency.environment', type: 'string', defaultValue: 'auto', description: 'Environment mode (auto/low_memory/high_memory)' },
  'adaptive_concurrency.sequential_threshold_mb': { key: 'adaptive_concurrency.sequential_threshold_mb', type: 'number', defaultValue: 2048, validate: (v) => v > 0, description: 'Sequential processing threshold in MB' },
  'adaptive_concurrency.parallel_threshold_mb': { key: 'adaptive_concurrency.parallel_threshold_mb', type: 'number', defaultValue: 8192, validate: (v) => v > 0, description: 'Parallel processing threshold in MB' },
  'adaptive_concurrency.max_concurrency': { key: 'adaptive_concurrency.max_concurrency', type: 'number', defaultValue: 5, validate: (v) => v > 0, description: 'Maximum concurrent operations' },

  // Watcher settings
  'watcher.debounce_ms': { key: 'watcher.debounce_ms', type: 'number', defaultValue: 2000, validate: (v) => v >= 0, description: 'File watcher debounce time in ms' },
};

/**
 * Validate a setting value against its schema definition
 */
export function validateSetting(key: string, value: any): { valid: boolean; error?: string } {
  const schema = SETTINGS_SCHEMA[key];
  
  // If no schema defined, allow any value (unknown settings)
  if (!schema) {
    return { valid: true };
  }

  // Type check
  if (typeof value !== schema.type) {
    return { 
      valid: false, 
      error: `Expected type '${schema.type}' but got '${typeof value}' for key '${key}'` 
    };
  }

  // Custom validation
  if (schema.validate && !schema.validate(value)) {
    return { 
      valid: false, 
      error: `Value ${value} failed validation for key '${key}'` 
    };
  }

  return { valid: true };
}

/**
 * Get schema definition for a setting
 */
export function getSettingSchema(key: string): SettingSchema | undefined {
  return SETTINGS_SCHEMA[key];
}

/**
 * Get all registered settings with their schemas
 */
export function getAllSettingsWithSchemas(): Record<string, SettingSchema> {
  return { ...SETTINGS_SCHEMA };
}
