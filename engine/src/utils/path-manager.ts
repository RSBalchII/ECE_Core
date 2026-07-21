/**
 * Path Manager - Centralized Path Resolution for Anchor Engine
 *
 * Implements Standard 051: Service Module Path Resolution
 * Ensures consistent path handling across all platforms
 */

import * as path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';
import { PATHS } from '../config/paths.js';

const __filename = fileURLToPath(import.meta.url);
// const __dirname = path.dirname(__filename); // Not used, commented out to avoid TS error
const require = createRequire(import.meta.url);

export class PathManager {
  private static instance: PathManager;
  private readonly basePath: string;
  private readonly platform: NodeJS.Platform;

  private constructor() {
    // Determine base path based on execution context
    if (typeof process !== 'undefined' && (process as any).resourcesPath) {
      // Electron environment
      this.basePath = (process as any).resourcesPath;
    } else if (typeof process !== 'undefined') {
      // Node.js environment
      // In ES modules, __dirname is not available, so we use import.meta.url
      const __filename = fileURLToPath(import.meta.url);
      const __dirname = path.dirname(__filename);
      this.basePath = path.resolve(__dirname, '../..');
    } else {
      // Fallback
      this.basePath = (process as any).cwd();
    }

    this.platform = process.platform;
    console.log(`[PathManager] Initialized. BasePath: ${this.basePath}, Platform: ${this.platform}`);
  }

  public static getInstance(): PathManager {
    if (!PathManager.instance) {
      PathManager.instance = new PathManager();
      console.log('[PathManager] Singleton instance created.');
    }
    return PathManager.instance;
  }

  /**
   * Get the base path (public accessor)
   */
  public getBasePath(): string {
    return this.basePath;
  }

  /**
   * Resolve native binary paths based on environment and platform
   */
  public getNativePath(filename: string): string {
    // Handle platform-specific binary names
    let platformBinary = filename;

    if (filename.startsWith('cozo_node_')) {
      // Already platform-specific
      platformBinary = filename;
    } else if (filename === 'cozo_lib.node') {
      // Map generic name to platform-specific
      switch (this.platform) {
        case 'win32':
          platformBinary = 'cozo_node_win32.node';
          break;
        case 'darwin':
          platformBinary = 'cozo_node_darwin.node';
          break;
        case 'linux':
          platformBinary = 'cozo_node_linux.node';
          break;
        default:
          throw new Error(`Unsupported platform: ${this.platform}`);
      }
    } else if (filename === 'ece_native.node') {
      // For our custom native module
      switch (this.platform) {
        case 'win32':
          platformBinary = path.join(this.basePath, 'build', 'Release', 'ece_native.node');
          break;
        case 'darwin':
        case 'linux':
          platformBinary = path.join(this.basePath, 'build', 'Release', 'ece_native.node');
          break;
        default:
          throw new Error(`Unsupported platform: ${this.platform}`);
      }
    }

    const resolvedPath = path.resolve(this.basePath, platformBinary);
    console.log(`[PathManager] Resolving ${filename} -> ${resolvedPath}`);
    return resolvedPath;
  }

  /**
   * Get database path (PGlite directory)
   */
  public getDatabasePath(): string {
    return PATHS.CONTEXT_DATA_DIR;
  }

  /**
   * Get database directory (for SQLite3 context.db location)
   */
  public getDatabaseDir(): string {
    return this.getDatabasePath();
  }

  /**
   * Get notebook directory path
   */
  public getNotebookDir(): string {
    return PATHS.NOTEBOOK_DIR;
  }

  /**
   * Get context directory path (Internal Configuration/Tags)
   */
  public getContextDir(): string {
    return PATHS.CONTEXT_DIR;
  }

  /**
   * Get models directory path
   */
  public getModelsDir(): string {
    return PATHS.MODELS_DIR;
  }

  /**
   * Get logs directory path
   */
  public getLogsDir(): string {
    return PATHS.LOGS_DIR;
  }

  /**
   * Get specs directory path
   */
  public getSpecsDir(): string {
    return path.resolve(this.basePath, '..', 'specs');
  }

  /**
   * Normalize a file path (cross-platform compatible)
   */
  public normalizePath(filePath: string): string {
    // Use path.normalize for cross-platform compatibility
    return path.normalize(filePath);
  }

  /**
   * Get user settings path
   */
  public getUserSettingsPath(): string {
    return PATHS.USER_SETTINGS;
  }

  /**
   * Get sovereign tags path
   */
  public getSovereignTagsPath(): string {
    return path.resolve(this.getContextDir(), 'internal_tags.json');
  }
}

// Export singleton instance
export const pathManager = PathManager.getInstance();