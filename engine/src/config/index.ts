/**
 * Configuration Module for Sovereign Context Engine
 * 
 * This module manages all configuration for the context engine including
 * paths, model settings, and system parameters.
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import yaml from 'js-yaml';
import { ZodError } from 'zod';

// For __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Import Zod schema for validation
import { ConfigSchema, UserSettingsSchema, safeValidateConfig } from './schema.js';

// Re-export types from schema
export type { Config, UserSettings } from './schema.js';
export { validateConfig, validateUserSettings, safeValidateConfig, ConfigSchema } from './schema.js';

// Define configuration interface (kept for backward compatibility, types now from schema)
interface Config {
  // Core
  PORT: number;
  HOST: string;
  API_KEY: string;
  LOG_LEVEL: string;
  OVERLAY_PORT: number;

  // LLM Provider
  LLM_PROVIDER: 'local' | 'remote';
  REMOTE_LLM_URL: string;
  REMOTE_MODEL_NAME: string;
  LLM_MODEL_DIR: string;

  // Tuning
  DEFAULT_SEARCH_CHAR_LIMIT: number;
  SIMILARITY_THRESHOLD: number;
  TOKEN_LIMIT: number;

  VECTOR_INGEST_BATCH: number;

  // Resource Management
  GC_COOLDOWN_MS: number;
  MAX_ATOMS_IN_MEMORY: number;
  MONITORING_INTERVAL_MS: number;

  // Watcher Settings
  WATCHER_DEBOUNCE_MS: number;
  WATCHER_STABILITY_THRESHOLD_MS: number;
  WATCHER_EXTRA_PATHS: string[];

  // Context Relevance
  CONTEXT_RELEVANCE_WEIGHT: number;
  CONTEXT_RECENCY_WEIGHT: number;

  // Infrastructure
  REDIS: {
    ENABLED: boolean;
    URL: string;
    TTL: number;
  };
  NEO4J: {
    ENABLED: boolean;
    URI: string;
    USER: string;
    PASS: string;
  };

  // Features
  FEATURES: {
    CONTEXT_STORAGE: boolean;
    MEMORY_RECALL: boolean;
    CODA: boolean;
    ARCHIVIST: boolean;
    WEAVER: boolean;
    MARKOVIAN: boolean;
  };

  // Search Settings
  SEARCH: {
    strategy: string;
    hide_years_in_tags: boolean;
    whitelist: string[];
    max_chars_default: number;
    max_chars_limit: number;
    fts_window_size: number;
    fts_padding: number;
  };

  // Models
  MODELS: {
    EMBEDDING_DIM: number;
    MAIN: {
      PATH: string;
      CTX_SIZE: number;
      GPU_LAYERS: number;
      MAX_TOKENS: number;
    };
    ORCHESTRATOR: {
      PATH: string;
      CTX_SIZE: number;
      GPU_LAYERS: number;
      MAX_TOKENS: number;
    };
    VISION: {
      PATH: string;
      PROJECTOR: string;
      CTX_SIZE: number;
      GPU_LAYERS: number;
      MAX_TOKENS: number;
    };
  };

  // Services
  SERVICES: {
    VISION_SERVER_PORT: number;
    CHAT_SERVER_PORT: number;
    TAG_INFECTOR_UNLOAD_TIMEOUT: number;
    TAG_GLINER_CHECK_INTERVAL: number;
  };

  // Limits and Thresholds
  LIMITS: {
    MAX_FILE_SIZE_BYTES: number;
    MAX_CONTENT_LENGTH_CHARS: number;
    MAX_CHUNK_SIZE_CHARS: number;
    MAX_SUMMARY_LENGTH_CHARS: number;
    DATE_EXTRACTOR_SCAN_LIMIT: number;
  };

  // Database Settings
  DATABASE: {
    WIPE_ON_STARTUP: boolean; // Standard 051: Ephemeral Index (true = wipe & rebuild on each start)
  };

  // Adaptive Concurrency (Standard 132)
  ADAPTIVE_CONCURRENCY: {
    SEQUENTIAL_THRESHOLD_MB: number;
    PARALLEL_THRESHOLD_MB: number;
    MAX_CONCURRENCY: number;
    LOW_MEMORY_BATCH_SIZE: number;
    HIGH_MEMORY_BATCH_SIZE: number;
    FORCE_SEQUENTIAL: boolean;
    FORCE_PARALLEL: boolean;
  };

  // Memory Management (Standard 127/134/135)
  MEMORY: {
    HEAP_PRESSURE_MB: number;
    THROTTLE_START_MB: number;
    THROTTLE_MAX_MB: number;
    EMERGENCY_STOP_MB: number;
    SEARCH_RESULTS_BATCH_SIZE: number;
    ENABLE_STREAMING_RESULTS: boolean;
  };
}

// Default configuration
const DEFAULT_CONFIG: Config = {
  // Core
  PORT: 3160,
  HOST: "0.0.0.0",
  API_KEY: "",  // Empty by default - must be explicitly configured
  LOG_LEVEL: "INFO",
  OVERLAY_PORT: 3002,

  // LLM Provider
  LLM_PROVIDER: 'local',
  REMOTE_LLM_URL: "http://localhost:8000/v1",
  REMOTE_MODEL_NAME: "default",
  LLM_MODEL_DIR: "models",

  // Tuning
  DEFAULT_SEARCH_CHAR_LIMIT: 524288,
  SIMILARITY_THRESHOLD: 0.8,
  TOKEN_LIMIT: 1000000,

  VECTOR_INGEST_BATCH: 50,

  // Resource Management
  GC_COOLDOWN_MS: 30000, // 30 seconds
  MAX_ATOMS_IN_MEMORY: 2000,
  MONITORING_INTERVAL_MS: 30000, // 30 seconds

  // Watcher Settings
  WATCHER_DEBOUNCE_MS: 2000,
  WATCHER_STABILITY_THRESHOLD_MS: 2000,
  WATCHER_EXTRA_PATHS: [],

  // Context Relevance
  CONTEXT_RELEVANCE_WEIGHT: 0.7,
  CONTEXT_RECENCY_WEIGHT: 0.3,

  // Infrastructure
  REDIS: {
    ENABLED: false,
    URL: "redis://localhost:6379",
    TTL: 3600
  },
  NEO4J: {
    ENABLED: false,
    URI: "bolt://localhost:7687",
    USER: "neo4j",
    PASS: "password"
  },

  // Features
  FEATURES: {
    CONTEXT_STORAGE: true,
    MEMORY_RECALL: true,
    CODA: true,
    ARCHIVIST: true,
    WEAVER: true,
    MARKOVIAN: true
  },

  // Search
  SEARCH: {
    strategy: "hybrid",
    hide_years_in_tags: true,
    whitelist: [],
    max_chars_default: 5000,   // 5k chars = ~1.25k tokens (mobile-friendly)
    max_chars_limit: 20000,    // 20k chars max limit
    fts_window_size: 1500,
    fts_padding: 750
  },

  // Models
  MODELS: {
    EMBEDDING_DIM: 768,
    MAIN: {
      PATH: "glm-edge-1.5b-chat.Q5_K_M.gguf", // Default from user_settings.json
      CTX_SIZE: 8192, // Default from user_settings.json
      GPU_LAYERS: 11, // Default from user_settings.json
      MAX_TOKENS: 1024
    },
    ORCHESTRATOR: {
      PATH: "Qwen3-4B-Function-Calling-Pro.gguf", // Default from user_settings.json
      CTX_SIZE: 8192,
      GPU_LAYERS: 0,
      MAX_TOKENS: 2048
    },
    VISION: {
      PATH: "",  // MUST BE SET IN user_settings.json
      PROJECTOR: "", // MUST BE SET IN user_settings.json
      CTX_SIZE: 2048,
      GPU_LAYERS: 11, // Default from user_settings.json
      MAX_TOKENS: 1024
    }
  },

  // Services
  SERVICES: {
    VISION_SERVER_PORT: 8081,
    CHAT_SERVER_PORT: 8080,
    TAG_INFECTOR_UNLOAD_TIMEOUT: 300000, // 5 minutes
    TAG_GLINER_CHECK_INTERVAL: 60000 // 1 minute
  },

  // Limits and Thresholds
  LIMITS: {
    MAX_FILE_SIZE_BYTES: 10485760, // 10MB
    MAX_CONTENT_LENGTH_CHARS: 5000,
    MAX_CHUNK_SIZE_CHARS: 3000,
    MAX_SUMMARY_LENGTH_CHARS: 2000,
    DATE_EXTRACTOR_SCAN_LIMIT: 2000
  },

  // Database Settings
  DATABASE: {
    // Standard 051: Ephemeral Index
    // Default true: wipe PGlite index on each startup so it rebuilds from mirrored_brain/.
    // Set false to retain the index across restarts (faster startup, but risks stale/corrupt data).
    WIPE_ON_STARTUP: true
  },

  // Adaptive Concurrency (Standard 132)
  // Automatically adjusts parallel processing based on available memory
  ADAPTIVE_CONCURRENCY: {
    // Memory threshold in MB below which to use sequential processing (default: 2048)
    SEQUENTIAL_THRESHOLD_MB: parseInt(process.env['ANCHOR_SEQUENTIAL_THRESHOLD_MB'] || '2048', 10),
    // Memory threshold in MB above which to use full parallel processing (default: 8192)
    PARALLEL_THRESHOLD_MB: parseInt(process.env['ANCHOR_PARALLEL_THRESHOLD_MB'] || '8192', 10),
    // Maximum concurrent operations in adaptive mode (default: 5)
    MAX_CONCURRENCY: parseInt(process.env['ANCHOR_MAX_CONCURRENCY'] || '5', 10),
    // Batch size for low-memory mode (default: 1)
    LOW_MEMORY_BATCH_SIZE: parseInt(process.env['ANCHOR_LOW_MEMORY_BATCH_SIZE'] || '1', 10),
    // Batch size for high-memory mode (default: 20)
    HIGH_MEMORY_BATCH_SIZE: parseInt(process.env['ANCHOR_HIGH_MEMORY_BATCH_SIZE'] || '20', 10),
    // Force sequential mode regardless of memory (default: false)
    FORCE_SEQUENTIAL: process.env['ANCHOR_FORCE_SEQUENTIAL'] === 'true',
    // Force parallel mode regardless of memory (default: false)
    FORCE_PARALLEL: process.env['ANCHOR_FORCE_PARALLEL'] === 'true'
  },

  // Memory Management (Standard 127/134/135)
  // Configurable memory thresholds for search throttling and streaming
  MEMORY: {
    // Heap pressure threshold for downgrading max-recall to standard (default: 500MB)
    HEAP_PRESSURE_MB: parseInt(process.env['ANCHOR_HEAP_PRESSURE_MB'] || '500', 10),
    // Start throttling searches at this heap size (default: 800MB)
    THROTTLE_START_MB: parseInt(process.env['ANCHOR_THROTTLE_START_MB'] || '800', 10),
    // Reject searches above this heap size (default: 1200MB)
    THROTTLE_MAX_MB: parseInt(process.env['ANCHOR_THROTTLE_MAX_MB'] || '1200', 10),
    // Emergency stop searches at this heap size (default: 1500MB)
    EMERGENCY_STOP_MB: parseInt(process.env['ANCHOR_EMERGENCY_STOP_MB'] || '1500', 10),
    // Batch size for streaming search results (default: 20)
    SEARCH_RESULTS_BATCH_SIZE: parseInt(process.env['ANCHOR_SEARCH_RESULTS_BATCH_SIZE'] || '20', 10),
    // Enable streaming results for memory efficiency (default: false)
    ENABLE_STREAMING_RESULTS: process.env['ANCHOR_ENABLE_STREAMING_RESULTS'] === 'true'
  }
};

// Configuration loader
function loadConfig(): Config {
  // Determine config file path
  // Priority: user_settings.json > sovereign.yaml > .env > Defaults

  let loadedConfig = { ...DEFAULT_CONFIG };

  // 1. Try Loading sovereign.yaml (Legacy/System Config)
  const configPath = process.env['SOVEREIGN_CONFIG_PATH'] ||
    path.join(__dirname, '..', '..', 'sovereign.yaml') ||
    path.join(__dirname, '..', 'config', 'default.yaml');

  if (fs.existsSync(configPath)) {
    try {
      const configFile = fs.readFileSync(configPath, 'utf8');
      const parsedConfig = yaml.load(configFile) as Partial<Config>;
      loadedConfig = { ...loadedConfig, ...parsedConfig };
    } catch (error) {
      console.warn(`Failed to load config from ${configPath}:`, error);
    }
  }

  // 2. Try Loading user_settings.json (Highest Priority for User Overrides)
  // First try the root of the anchor-os project (monorepo setup)
  const userSettingsPath = path.join(__dirname, '..', '..', '..', 'user_settings.json');
  if (fs.existsSync(userSettingsPath) && fs.statSync(userSettingsPath).isFile()) {
    try {
      const userSettings = JSON.parse(fs.readFileSync(userSettingsPath, 'utf8'));
      console.log(`[Config] Loaded settings from ${userSettingsPath}`);

      // Load LLM Settings (Provider + Model paths — single consolidated block)
      if (userSettings.llm) {
        // Provider settings
        if (userSettings.llm.provider) loadedConfig.LLM_PROVIDER = userSettings.llm.provider;
        if (userSettings.llm.remote_url) loadedConfig.REMOTE_LLM_URL = userSettings.llm.remote_url;
        if (userSettings.llm.remote_model) loadedConfig.REMOTE_MODEL_NAME = userSettings.llm.remote_model;
        if (userSettings.llm.model_dir) loadedConfig.LLM_MODEL_DIR = userSettings.llm.model_dir;

        // Main model
        if (userSettings.llm.chat_model) loadedConfig.MODELS.MAIN.PATH = userSettings.llm.chat_model;
        if (userSettings.llm.gpu_layers !== undefined) loadedConfig.MODELS.MAIN.GPU_LAYERS = userSettings.llm.gpu_layers;
        if (userSettings.llm.ctx_size !== undefined) loadedConfig.MODELS.MAIN.CTX_SIZE = userSettings.llm.ctx_size;
        if (userSettings.llm.max_tokens !== undefined) loadedConfig.MODELS.MAIN.MAX_TOKENS = userSettings.llm.max_tokens;

        // Orchestrator model
        if (userSettings.llm.task_model) loadedConfig.MODELS.ORCHESTRATOR.PATH = userSettings.llm.task_model;
        if (userSettings.llm.orchestrator_ctx_size !== undefined) loadedConfig.MODELS.ORCHESTRATOR.CTX_SIZE = userSettings.llm.orchestrator_ctx_size;
        if (userSettings.llm.orchestrator_gpu_layers !== undefined) loadedConfig.MODELS.ORCHESTRATOR.GPU_LAYERS = userSettings.llm.orchestrator_gpu_layers;
        if (userSettings.llm.orchestrator_max_tokens !== undefined) loadedConfig.MODELS.ORCHESTRATOR.MAX_TOKENS = userSettings.llm.orchestrator_max_tokens;

        // Vision model
        if (userSettings.llm.vision_model) loadedConfig.MODELS.VISION.PATH = userSettings.llm.vision_model;
        if (userSettings.llm.vision_projector) loadedConfig.MODELS.VISION.PROJECTOR = userSettings.llm.vision_projector;
        if (userSettings.llm.vision_ctx_size !== undefined) loadedConfig.MODELS.VISION.CTX_SIZE = userSettings.llm.vision_ctx_size;
        if (userSettings.llm.vision_gpu_layers !== undefined) loadedConfig.MODELS.VISION.GPU_LAYERS = userSettings.llm.vision_gpu_layers;
        if (userSettings.llm.vision_max_tokens !== undefined) loadedConfig.MODELS.VISION.MAX_TOKENS = userSettings.llm.vision_max_tokens;
      }

      // Load Search Settings (single consolidated block)
      if (userSettings.search) {
        if (userSettings.search.strategy) loadedConfig.SEARCH.strategy = userSettings.search.strategy;
        if (userSettings.search.hide_years_in_tags !== undefined) loadedConfig.SEARCH.hide_years_in_tags = userSettings.search.hide_years_in_tags;
        if (userSettings.search.whitelist) loadedConfig.SEARCH.whitelist = userSettings.search.whitelist;
        if (userSettings.search.max_chars_default !== undefined) loadedConfig.SEARCH.max_chars_default = userSettings.search.max_chars_default;
        if (userSettings.search.max_chars_limit !== undefined) loadedConfig.SEARCH.max_chars_limit = userSettings.search.max_chars_limit;
        if (userSettings.search.fts_window_size !== undefined) loadedConfig.SEARCH.fts_window_size = userSettings.search.fts_window_size;
        if (userSettings.search.fts_padding !== undefined) loadedConfig.SEARCH.fts_padding = userSettings.search.fts_padding;
      }

      // Load Server Settings
      if (userSettings.server) {
        if (userSettings.server.host) loadedConfig.HOST = userSettings.server.host;
        if (userSettings.server.port) loadedConfig.PORT = userSettings.server.port;
        if (userSettings.server.api_key !== undefined) loadedConfig.API_KEY = userSettings.server.api_key;
      }

      // Load Resource Management Settings
      if (userSettings.resource_management) {
        if (userSettings.resource_management.gc_cooldown_ms !== undefined) loadedConfig.GC_COOLDOWN_MS = userSettings.resource_management.gc_cooldown_ms;
        if (userSettings.resource_management.max_atoms_in_memory !== undefined) loadedConfig.MAX_ATOMS_IN_MEMORY = userSettings.resource_management.max_atoms_in_memory;
        if (userSettings.resource_management.monitoring_interval_ms !== undefined) loadedConfig.MONITORING_INTERVAL_MS = userSettings.resource_management.monitoring_interval_ms;
      }

      // Load Watcher Settings
      if (userSettings.watcher) {
        if (userSettings.watcher.debounce_ms !== undefined) loadedConfig.WATCHER_DEBOUNCE_MS = userSettings.watcher.debounce_ms;
        if (userSettings.watcher.stability_threshold_ms !== undefined) loadedConfig.WATCHER_STABILITY_THRESHOLD_MS = userSettings.watcher.stability_threshold_ms;
        if (userSettings.watcher.extra_paths) loadedConfig.WATCHER_EXTRA_PATHS = userSettings.watcher.extra_paths;
      }

      // Load Context Relevance Settings
      if (userSettings.context) {
        if (userSettings.context.relevance_weight !== undefined) loadedConfig.CONTEXT_RELEVANCE_WEIGHT = userSettings.context.relevance_weight;
        if (userSettings.context.recency_weight !== undefined) loadedConfig.CONTEXT_RECENCY_WEIGHT = userSettings.context.recency_weight;
      }

      // Load Service Settings
      if (userSettings.services) {
        if (userSettings.services.vision_server_port !== undefined) loadedConfig.SERVICES.VISION_SERVER_PORT = userSettings.services.vision_server_port;
        if (userSettings.services.chat_server_port !== undefined) loadedConfig.SERVICES.CHAT_SERVER_PORT = userSettings.services.chat_server_port;
        if (userSettings.services.tag_infector_unload_timeout !== undefined) loadedConfig.SERVICES.TAG_INFECTOR_UNLOAD_TIMEOUT = userSettings.services.tag_infector_unload_timeout;
        if (userSettings.services.tag_gliner_check_interval !== undefined) loadedConfig.SERVICES.TAG_GLINER_CHECK_INTERVAL = userSettings.services.tag_gliner_check_interval;
      }

      // Load Database Settings
      if (userSettings.database) {
        if (userSettings.database.wipe_on_startup !== undefined) loadedConfig.DATABASE.WIPE_ON_STARTUP = userSettings.database.wipe_on_startup;
      }

      // Load Limits and Thresholds
      if (userSettings.limits) {
        if (userSettings.limits.max_file_size_bytes !== undefined) loadedConfig.LIMITS.MAX_FILE_SIZE_BYTES = userSettings.limits.max_file_size_bytes;
        if (userSettings.limits.max_content_length_chars !== undefined) loadedConfig.LIMITS.MAX_CONTENT_LENGTH_CHARS = userSettings.limits.max_content_length_chars;
        if (userSettings.limits.max_chunk_size_chars !== undefined) loadedConfig.LIMITS.MAX_CHUNK_SIZE_CHARS = userSettings.limits.max_chunk_size_chars;
        if (userSettings.limits.max_summary_length_chars !== undefined) loadedConfig.LIMITS.MAX_SUMMARY_LENGTH_CHARS = userSettings.limits.max_summary_length_chars;
        if (userSettings.limits.date_extractor_scan_limit !== undefined) loadedConfig.LIMITS.DATE_EXTRACTOR_SCAN_LIMIT = userSettings.limits.date_extractor_scan_limit;
      }

      // Load Memory Management Settings (Standard 127/134/135)
      if (userSettings.memory) {
        if (userSettings.memory.heap_pressure_mb !== undefined) loadedConfig.MEMORY.HEAP_PRESSURE_MB = userSettings.memory.heap_pressure_mb;
        if (userSettings.memory.throttle_start_mb !== undefined) loadedConfig.MEMORY.THROTTLE_START_MB = userSettings.memory.throttle_start_mb;
        if (userSettings.memory.throttle_max_mb !== undefined) loadedConfig.MEMORY.THROTTLE_MAX_MB = userSettings.memory.throttle_max_mb;
        if (userSettings.memory.emergency_stop_mb !== undefined) loadedConfig.MEMORY.EMERGENCY_STOP_MB = userSettings.memory.emergency_stop_mb;
        if (userSettings.memory.search_results_batch_size !== undefined) loadedConfig.MEMORY.SEARCH_RESULTS_BATCH_SIZE = userSettings.memory.search_results_batch_size;
        if (userSettings.memory.enable_streaming_results !== undefined) loadedConfig.MEMORY.ENABLE_STREAMING_RESULTS = userSettings.memory.enable_streaming_results;
      }

    } catch (e) {
      console.error(`[Config] Failed to parse user_settings.json:`, e);
    }
  }

  // Validate the final configuration using Zod
  const validationResult = safeValidateConfig(loadedConfig);
  
  if (!validationResult.success) {
    console.error('[Config] Configuration validation failed:');
    validationResult.error.errors.forEach(err => {
      console.error(`  - ${err.path.join('.')}: ${err.message}`);
    });
    console.warn('[Config] Using default configuration with validation errors. Fix user_settings.json to resolve.');
  } else {
    console.log('[Config] Configuration validated successfully');
  }

  return loadedConfig;
}

// Export configuration
export const config = loadConfig();

export default config;