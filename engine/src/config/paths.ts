/**
 * Path Configuration for Sovereign Context Engine
 *
 * All paths are abstracted to ~/.anchor/user_settings.json.
 * No config files or output directories live in the project root.
 *
 * Priority: Environment variables > user_settings.json > defaults
 */

import * as path from 'path';
import { homedir } from 'os';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Define base paths
// __dirname is engine/src/config, so we need to go up 3 levels to reach project root
export const PROJECT_ROOT = path.resolve(process.env.PROJECT_ROOT || path.join(__dirname, '..', '..', '..'));

// Load user_settings.json for path overrides
let userSettings: any = {};

// Define Anchor root (centralized user data) - in user's home directory (~/.anchor)
// This matches the standard config location (~/.config, ~/.gitconfig, etc.)
const ANCHOR_ROOT = path.resolve(
  process.env.ANCHOR_ROOT ||
  path.join(homedir(), '.anchor')
);

// Fallback base directory under .anchor for data directories.
// When user_settings.json provides absolute paths, they take precedence.
const FALLBACK_DATA_DIR = path.join(ANCHOR_ROOT, 'local-data');

// Load user_settings.json from .anchor/ (primary) or project root (fallback)
try {
  const anchorSettingsPath = path.join(ANCHOR_ROOT, 'user_settings.json');
  const projectSettingsPath = path.join(PROJECT_ROOT, 'user_settings.json');
  const settingsPath = fs.existsSync(anchorSettingsPath) ? anchorSettingsPath : projectSettingsPath;
  if (fs.existsSync(settingsPath)) {
    userSettings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
  }
} catch (e) {
  // Ignore errors - will use defaults
}

// Helper: resolve a path from user_settings override or fallback default
function resolveDataDir(key: string): string {
  const override = userSettings.paths?.[key];
  if (override && typeof override === 'string') {
    return path.resolve(override);
  }
  return path.join(FALLBACK_DATA_DIR, key);
}

// Path configuration with user_settings.json overrides
// Priority: Environment variables > user_settings.json > defaults

export const CONTEXT_DIR = process.env.CONTEXT_DIR || resolveDataDir('context');
export const DIST_DIR = process.env.DIST_DIR || resolveDataDir('dist');
export const BASE_PATH = PROJECT_ROOT;

// Standard 110: Logs directory under .anchor for centralized logging
export const LOGS_DIR = path.resolve(
  process.env.LOGS_DIR ||
  userSettings.paths?.logs ||
  path.join(ANCHOR_ROOT, 'logs')
);

// Context data directory under .anchor for database storage
export const CONTEXT_DATA_DIR = path.resolve(
  process.env.CONTEXT_DATA_DIR ||
  userSettings.paths?.context_data ||
  path.join(ANCHOR_ROOT, 'context_data')
);

// Test database directory under .anchor for test artifacts
export const TEST_DBS_DIR = path.resolve(
  process.env.TEST_DBS_DIR ||
  userSettings.paths?.test_dbs ||
  path.join(ANCHOR_ROOT, 'test-dbs')
);

// Define specific paths
export const PATHS = {
  PROJECT_ROOT,
  ANCHOR_ROOT,
  FALLBACK_DATA_DIR,
  CONTEXT_DIR,
  DIST_DIR,
  BACKUPS_DIR: path.resolve(process.env.BACKUPS_DIR || userSettings.paths?.backups || path.join(ANCHOR_ROOT, 'backups')),
  LOGS_DIR,
  CONTEXT_DATA_DIR,
  TEST_DBS_DIR,
  CONFIG_FILE: path.join(FALLBACK_DATA_DIR, 'sovereign.yaml'),
  USER_SETTINGS: path.join(ANCHOR_ROOT, 'user_settings.json'),
  DATABASE_FILE: path.join(CONTEXT_DIR, 'context.db'),
  // Standard 110: Centralized user data paths under local-data/
  INBOX_DIR: path.resolve(process.env.INBOX_DIR || userSettings.paths?.inbox || path.join(FALLBACK_DATA_DIR, 'inbox')),
  EXTERNAL_INBOX_DIR: path.resolve(process.env.EXTERNAL_INBOX_DIR || userSettings.paths?.external_inbox || path.join(FALLBACK_DATA_DIR, 'external-inbox')),
  DISTILLS_DIR: path.resolve(process.env.DISTILLS_DIR || userSettings.paths?.distills || path.join(FALLBACK_DATA_DIR, 'distills')),
  MIRRORED_BRAIN_DIR: path.resolve(process.env.MIRRORED_BRAIN_DIR || userSettings.paths?.mirrored_brain || path.join(ANCHOR_ROOT, 'mirror_brain')),
  SESSIONS_DIR: path.resolve(process.env.SESSIONS_DIR || userSettings.paths?.sessions || path.join(FALLBACK_DATA_DIR, 'sessions')),
  LIBRARIES_DIR: path.join(CONTEXT_DIR, 'libraries'),
  MIRRORS_DIR: path.join(CONTEXT_DIR, 'mirrors'),
  ENGINE_BIN: path.join(PROJECT_ROOT, 'engine', 'bin'),
  ENGINE_SRC: path.join(PROJECT_ROOT, 'engine', 'src'),
  ENGINE_DIST: path.join(PROJECT_ROOT, 'engine', 'dist'),
  ENGINE_CONTEXT: path.join(FALLBACK_DATA_DIR, 'engine-context'),
  ENGINE_PLUGINS: path.join(PROJECT_ROOT, 'engine', 'plugins'),
  DESKTOP_OVERLAY_SRC: path.join(PROJECT_ROOT, 'packages', 'desktop-overlay', 'src'),
  DESKTOP_OVERLAY_DIST: path.join(PROJECT_ROOT, 'packages', 'desktop-overlay', 'dist'),
};

// Ensure anchor root and subdirectories exist
try {
  fs.mkdirSync(ANCHOR_ROOT, { recursive: true });

  // Create subdirectories if they don't exist
  const subdirs = ['inbox', 'external-inbox', 'distills', 'mirrored_brain', 'sessions', 'logs', 'backups', 'context', 'models', 'dist', 'context_data', 'test-dbs'];
  for (const subdir of subdirs) {
    const subdirPath = path.join(FALLBACK_DATA_DIR, subdir);
    if (!fs.existsSync(subdirPath)) {
      fs.mkdirSync(subdirPath, { recursive: true });
    }
  }

  // Create directories directly under ANCHOR_ROOT
  const anchorSubdirs = ['context_data', 'test-dbs'];
  for (const subdir of anchorSubdirs) {
    const subdirPath = path.join(ANCHOR_ROOT, subdir);
    if (!fs.existsSync(subdirPath)) {
      fs.mkdirSync(subdirPath, { recursive: true });
    }
  }
} catch (e) {
  // Ignore errors - directories may already exist
}

// Export individual paths for convenience
export const {
  BACKUPS_DIR,
  INBOX_DIR,
  EXTERNAL_INBOX_DIR,
  DISTILLS_DIR,
  MIRRORED_BRAIN_DIR,
  ENGINE_CONTEXT,
  ENGINE_PLUGINS,
  DESKTOP_OVERLAY_SRC,
  DESKTOP_OVERLAY_DIST,
} = PATHS;

// Export provenance configuration
export const DEFAULT_PROVENANCE = path.resolve(
  process.env.DEFAULT_PROVENANCE ||
  userSettings.paths?.default_provenance ||
  'internal'
);

export default PATHS;
