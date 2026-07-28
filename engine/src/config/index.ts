/**
 * Configuration Module for Sovereign Context Engine
 *
 * All configuration is abstracted to ~/.anchor/user_settings.json.
 * No config files live in the project root.
 */

import * as fs from 'fs';
import * as path from 'path';
import { homedir } from 'os';
import { fileURLToPath } from 'url';
import yaml from 'js-yaml';
import { z } from 'zod';
import { PATHS } from './paths.js';

// For __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// === Configuration Schema with Zod Validation ===

// Server Settings Schema
const ServerSettingsSchema = z.object({
  host: z.string().optional(),
  port: z.number().int().min(1).max(65535).optional(),
  // SECURITY FIX (Standard 132): API key must be at least 32 chars with mixed character types
  // Prevents weak keys like "aaaaaaaaaaaaaaaa" or "1234567890123456"
  // Accepts: mixed case+digit OR 64+ char hex key (from crypto.randomBytes)
  api_key: z.string()
    .min(32, 'API key must be at least 32 characters')
    .max(128, 'API key must not exceed 128 characters')
    .regex(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z0-9]{32,128}$|^[a-f0-9]{64,}$/i,
      'API key must be 32-128 alphanumeric chars with mixed case+digit - OR 64+ char hex')
    .optional(),
});

// Resource Management Schema
const ResourceManagementSchema = z.object({
  gc_cooldown_ms: z.number().int().positive().optional(),
  max_atoms_in_memory: z.number().int().positive().optional(),
  monitoring_interval_ms: z.number().int().positive().optional(),
  cache_ttl_ms: z.number().int().positive().optional(),
  max_cache_size: z.number().int().positive().optional(),
});

// Watcher Settings Schema
const WatcherSettingsSchema = z.object({
  debounce_ms: z.number().int().positive().optional(),
  stability_threshold_ms: z.number().int().positive().optional(),
  extra_paths: z.array(z.string()).optional(),
  auto_start: z.boolean().optional(),
  wipe_mirrored_brain_on_shutdown: z.boolean().optional(),
});

// Search Settings Schema
const SearchSettingsSchema = z.object({
  strategy: z.string().optional(),
  hide_years_in_tags: z.boolean().optional(),
  whitelist: z.array(z.string()).optional(),
  max_chars_default: z.number().int().positive().optional(),
  max_chars_limit: z.number().int().positive().optional(),
  fts_window_size: z.number().int().positive().optional(),
  fts_padding: z.number().int().positive().optional(),
});

// Database Settings Schema
const DatabaseSettingsSchema = z.object({
  wipe_on_startup: z.boolean().optional(),
  wipe_on_shutdown: z.boolean().optional(),
  shared_buffers_mb: z.number().int().positive().optional(),
  effective_cache_size_mb: z.number().int().positive().optional(),
  work_mem_mb: z.number().int().positive().optional(),
  maintenance_work_mem_mb: z.number().int().positive().optional(),
});

// Memory Settings Schema
const MemorySettingsSchema = z.object({
  heap_pressure_mb: z.number().int().positive().optional(),
  throttle_start_mb: z.number().int().positive().optional(),
  throttle_max_mb: z.number().int().positive().optional(),
  emergency_stop_mb: z.number().int().positive().optional(),
  search_results_batch_size: z.number().int().positive().optional(),
  enable_streaming_results: z.boolean().optional(),
});

// Low Resource Mode Schema (Standard 136)
const LowResourceSchema = z.object({
  enabled: z.boolean().optional(),
  max_recall_low: z.number().int().min(1).optional(),
  max_recall_high: z.number().int().min(1).optional(),
  max_concurrency: z.number().int().min(1).optional(),
  search_batch_size: z.number().int().min(1).optional(),
  ingest_batch_size: z.number().int().min(1).optional(),
  vector_ingest_batch: z.number().int().min(1).optional(),
});

// Limits Schema
const LimitsSchema = z.object({
  max_file_size_bytes: z.number().int().positive().optional(),
  max_content_length_chars: z.number().int().positive().optional(),
  max_chunk_size_chars: z.number().int().positive().optional(),
  max_summary_length_chars: z.number().int().positive().optional(),
  date_extractor_scan_limit: z.number().int().positive().optional(),
});

// User Settings Schema (all optional, with defaults applied)
const _UserSettingsSchema = z.object({
  server: ServerSettingsSchema.optional(),
  resource_management: ResourceManagementSchema.optional(),
  watcher: WatcherSettingsSchema.optional(),
  search: SearchSettingsSchema.optional(),
  database: DatabaseSettingsSchema.optional(),
  memory: MemorySettingsSchema.optional(),
  low_resource: LowResourceSchema.optional(),
  limits: LimitsSchema.optional(),
  // Allow additional properties for backward compatibility
}).passthrough();

// Type inference from schema (used for type checking in loadConfig)
type _UserSettings = z.infer<typeof _UserSettingsSchema>;

// Define configuration interface
interface Config {
  // Core
  PORT: number;
  HOST: string;
  API_KEY: string;
  VERSION: string;
  GITHUB_TOKEN: string;
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
  CACHE_TTL_MS: number;
  MAX_CACHE_SIZE: number;

  // Low-Resource Mode (Standard 136)
  LOW_RESOURCE: {
    ENABLED: boolean;
    MAX_RECALL_LOW: number;
    MAX_RECALL_HIGH: number;
    MAX_CONCURRENCY: number;
    SEARCH_BATCH_SIZE: number;
    INGEST_BATCH_SIZE: number;
    VECTOR_INGEST_BATCH: number;
  };

  // Distiller Configuration (v2.1)
  DISTILLER: {
    SIMILARITY_THRESHOLD: number;
    OUTPUT_FORMAT: string;
  };

  // Watcher Settings
  WATCHER_DEBOUNCE_MS: number;
  WATCHER_STABILITY_THRESHOLD_MS: number;
  WATCHER_EXTRA_PATHS: string[];
  WATCHER_AUTO_START: boolean;
  WATCHER_WIPE_MIRRORED_BRAIN_ON_SHUTDOWN: boolean;

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

  // Watcher Settings
  WATCHER: {
    AUTO_START: boolean;
    WIPE_MIRRORED_BRAIN_ON_SHUTDOWN: boolean;
  };

  // Database Settings
  DATABASE: {
    WIPE_ON_STARTUP: boolean; // Standard 051: Ephemeral Index (true = wipe & rebuild on each start)
    WIPE_ON_SHUTDOWN: boolean;
    SHARED_BUFFERS_MB: number;
    EFFECTIVE_CACHE_SIZE_MB: number;
    WORK_MEM_MB: number;
    MAINTENANCE_WORK_MEM_MB: number;
    START_TIME: number; // Server start time for uptime calculation
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

  // Ingestion Configuration (Agent-Controlled)
  INGESTION: {
    CONCEPT_DENSITY: 'low' | 'medium' | 'high';
    TAG_THRESHOLD: number;
    DEDUP_STRENGTH: 'light' | 'medium' | 'aggressive';
    TOKEN_BUDGET_DEFAULT: number;
    INGESTION_PROFILE: 'code' | 'notes' | 'chat' | 'default';
  };

  // Density Query Configuration (Standard 086) — RAG tier thresholds for density queries
  DENSITY: {
    LIGHT_DOC_THRESHOLD: number;   // mol_count >= this → light tier (well-known concept)
    MEDIUM_DOC_THRESHOLD: number;  // mol_count >= this → medium tier
    LIGHT_RAG_LIMIT: number;       // doc limit to pass to external RAG for light tier
    MEDIUM_RAG_LIMIT: number;      // doc limit for medium tier
    HEAVY_RAG_LIMIT: number;       // doc limit for heavy tier (0 = all available)
  };
};

// Default configuration
const DEFAULT_CONFIG: Config = {
  // Core
  PORT: 3160,
  HOST: '0.0.0.0',
  API_KEY: '', // REQUIRED
  VERSION: '4.8.2', // Engine version - can be overridden in user_settings.json
  GITHUB_TOKEN: '', // Optional: GitHub PAT for repo ingestion: Must be set in user_settings.json -> server.api_key
  LOG_LEVEL: 'INFO',
  OVERLAY_PORT: 3002,

  // LLM Provider
  LLM_PROVIDER: 'local',
  REMOTE_LLM_URL: 'http://localhost:8000/v1',
  REMOTE_MODEL_NAME: 'default',
  LLM_MODEL_DIR: 'models',

  // Tuning
  DEFAULT_SEARCH_CHAR_LIMIT: 524288,
  SIMILARITY_THRESHOLD: 0.8,
  TOKEN_LIMIT: 1000000,

  VECTOR_INGEST_BATCH: 50,

  // Resource Management
  GC_COOLDOWN_MS: 30000, // 30 seconds
  MAX_ATOMS_IN_MEMORY: 2000,
  MONITORING_INTERVAL_MS: 30000, // 30 seconds
  CACHE_TTL_MS: 60000, // 60 seconds (1 minute)
  MAX_CACHE_SIZE: 500, // Increased from 100 to 500

  // Distiller Configuration (v2.1)
  DISTILLER: {
    SIMILARITY_THRESHOLD: 0.85,
    OUTPUT_FORMAT: 'decision-records',
  },

  // Watcher Settings
  WATCHER_DEBOUNCE_MS: 2000,
  WATCHER_STABILITY_THRESHOLD_MS: 2000,
  WATCHER_EXTRA_PATHS: [],
  WATCHER_AUTO_START: false,
  WATCHER_WIPE_MIRRORED_BRAIN_ON_SHUTDOWN: true,

  // Watcher Settings (nested object for index.ts access)
  WATCHER: {
    AUTO_START: false,
    WIPE_MIRRORED_BRAIN_ON_SHUTDOWN: true,
  },

  // Context Relevance
  CONTEXT_RELEVANCE_WEIGHT: 0.7,
  CONTEXT_RECENCY_WEIGHT: 0.3,

  // Infrastructure
  REDIS: {
    ENABLED: false,
    URL: 'redis://localhost:6379',
    TTL: 3600,
  },
  NEO4J: {
    ENABLED: false,
    URI: 'bolt://localhost:7687',
    USER: 'neo4j',
    PASS: 'password',
  },

  // Features
  FEATURES: {
    CONTEXT_STORAGE: true,
    MEMORY_RECALL: true,
    CODA: true,
    ARCHIVIST: true,
    WEAVER: true,
    MARKOVIAN: true,
  },

  // Search
  SEARCH: {
    strategy: 'hybrid',
    hide_years_in_tags: true,
    whitelist: [],
    max_chars_default: 5000,   // 5k chars = ~1.25k tokens (mobile-friendly)
    max_chars_limit: 20000,    // 20k chars max limit
    fts_window_size: 1500,
    fts_padding: 750,
  },

  // Models
  MODELS: {
    EMBEDDING_DIM: 768,
    MAIN: {
      PATH: 'glm-edge-1.5b-chat.Q5_K_M.gguf', // Default from user_settings.json
      CTX_SIZE: 8192, // Default from user_settings.json
      GPU_LAYERS: 11, // Default from user_settings.json
      MAX_TOKENS: 1024,
    },
    ORCHESTRATOR: {
      PATH: 'Qwen3-4B-Function-Calling-Pro.gguf', // Default from user_settings.json
      CTX_SIZE: 8192,
      GPU_LAYERS: 0,
      MAX_TOKENS: 2048,
    },
    VISION: {
      PATH: '',  // MUST BE SET IN user_settings.json
      PROJECTOR: '', // MUST BE SET IN user_settings.json
      CTX_SIZE: 2048,
      GPU_LAYERS: 11, // Default from user_settings.json
      MAX_TOKENS: 1024,
    },
  },

  // Services
  SERVICES: {
    VISION_SERVER_PORT: 8081,
    CHAT_SERVER_PORT: 8080,
    TAG_INFECTOR_UNLOAD_TIMEOUT: 300000, // 5 minutes
    TAG_GLINER_CHECK_INTERVAL: 60000, // 1 minute
  },

  // Limits and Thresholds
  LIMITS: {
    MAX_FILE_SIZE_BYTES: 10485760, // 10MB
    MAX_CONTENT_LENGTH_CHARS: 5000,
    MAX_CHUNK_SIZE_CHARS: 3000,
    MAX_SUMMARY_LENGTH_CHARS: 2000,
    DATE_EXTRACTOR_SCAN_LIMIT: 2000,
  },

  // Database Settings
  // Standard 127: PGlite Memory Optimization - tuned for 31k atoms
  // Increased from 64/128/8 to 256/512/32 for better cache performance
  DATABASE: {
    WIPE_ON_STARTUP: true,
    WIPE_ON_SHUTDOWN: true,
    SHARED_BUFFERS_MB: 256,   // SQLite shared buffer cache for index pages
    EFFECTIVE_CACHE_SIZE_MB: 512, // OS cache size hint for query planner
    WORK_MEM_MB: 32,          // In-memory sort buffer (larger = faster complex queries)
    MAINTENANCE_WORK_MEM_MB: 32,
    START_TIME: Date.now(),   // Server start time for uptime calculation
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
    FORCE_PARALLEL: process.env['ANCHOR_FORCE_PARALLEL'] === 'true',
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
    ENABLE_STREAMING_RESULTS: process.env['ANCHOR_ENABLE_STREAMING_RESULTS'] === 'true',
  },

  // Low-Resource Mode (Standard 136)
  // Optimizations for devices with limited memory/CPU
  LOW_RESOURCE: {
    // Enable low-resource mode (default: false)
    ENABLED: process.env['ANCHOR_LOW_RESOURCE_MODE'] === 'true',
    // Reduce max recall at low memory (default: 5)
    MAX_RECALL_LOW: parseInt(process.env['ANCHOR_MAX_RECALL_LOW'] || '5', 10),
    // Reduce max recall at high memory (default: 20)
    MAX_RECALL_HIGH: parseInt(process.env['ANCHOR_MAX_RECALL_HIGH'] || '20', 10),
    // Reduce concurrent operations (default: 1)
    MAX_CONCURRENCY: parseInt(process.env['ANCHOR_MAX_CONCURRENCY'] || '1', 10),
    // Reduce search result batch size (default: 10)
    SEARCH_BATCH_SIZE: parseInt(process.env['ANCHOR_SEARCH_BATCH_SIZE'] || '10', 10),
    // Reduce ingestion batch size (default: 5)
    INGEST_BATCH_SIZE: parseInt(process.env['ANCHOR_INGEST_BATCH_SIZE'] || '5', 10),
    // Reduce vector ingest batch (default: 10)
    VECTOR_INGEST_BATCH: parseInt(process.env['ANCHOR_VECTOR_INGEST_BATCH'] || '10', 10),
  },

  // Ingestion Configuration (Agent-Controlled)
  // Configurable ingestion behavior for different content types
  INGESTION: {
    CONCEPT_DENSITY: (process.env['ANCHOR_CONCEPT_DENSITY'] as 'low' | 'medium' | 'high') || 'medium',
    TAG_THRESHOLD: parseFloat(process.env['ANCHOR_TAG_THRESHOLD'] || '0.7'),
    DEDUP_STRENGTH: (process.env['ANCHOR_DEDUP_STRENGTH'] as 'light' | 'medium' | 'aggressive') || 'medium',
    TOKEN_BUDGET_DEFAULT: parseInt(process.env['ANCHOR_TOKEN_BUDGET_DEFAULT'] || '2000', 10),
    INGESTION_PROFILE: (process.env['ANCHOR_INGESTION_PROFILE'] as 'code' | 'notes' | 'chat' | 'default') || 'default',
  },

  // Density Query Configuration (Standard 086) — RAG tier thresholds for density queries
  DENSITY: {
    LIGHT_DOC_THRESHOLD: parseInt(process.env['ANCHOR_DENSITY_LIGHT_THRESHOLD'] || '50', 10),
    MEDIUM_DOC_THRESHOLD: parseInt(process.env['ANCHOR_DENSITY_MEDIUM_THRESHOLD'] || '5', 10),
    LIGHT_RAG_LIMIT: parseInt(process.env['ANCHOR_DENSITY_LIGHT_RAG_LIMIT'] || '10', 10),
    MEDIUM_RAG_LIMIT: parseInt(process.env['ANCHOR_DENSITY_MEDIUM_RAG_LIMIT'] || '25', 10),
    HEAVY_RAG_LIMIT: parseInt(process.env['ANCHOR_DENSITY_HEAVY_RAG_LIMIT'] || '0', 10), // 0 = all available
  },
};

// Configuration loader
function loadConfig(): Config {
  // Determine config file path
  // Priority: ~/.anchor/user_settings.json > ~/.anchor/sovereign.yaml > Defaults
  let loadedConfig = { ...DEFAULT_CONFIG };

  // 1. Try Loading sovereign.yaml (Legacy/System Config)
  const configPath = process.env.SOVEREIGN_CONFIG_PATH || PATHS.CONFIG_FILE;

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
  // Primary: ~/.anchor/user_settings.json (user's home directory)
  const anchorSettingsPath = PATHS.USER_SETTINGS;

  if (fs.existsSync(anchorSettingsPath) && fs.statSync(anchorSettingsPath).isFile()) {
    try {
      const userSettings = JSON.parse(fs.readFileSync(anchorSettingsPath, 'utf8'));
      console.log(`[Config] Loaded settings from ${anchorSettingsPath}`);

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
        if (userSettings.server.version !== undefined) loadedConfig.VERSION = userSettings.server.version;
        if (userSettings.github?.token !== undefined) loadedConfig.GITHUB_TOKEN = userSettings.github.token;
      }

      // Load Resource Management Settings
      if (userSettings.resource_management) {
        if (userSettings.resource_management.gc_cooldown_ms !== undefined) loadedConfig.GC_COOLDOWN_MS = userSettings.resource_management.gc_cooldown_ms;
        if (userSettings.resource_management.max_atoms_in_memory !== undefined) loadedConfig.MAX_ATOMS_IN_MEMORY = userSettings.resource_management.max_atoms_in_memory;
        if (userSettings.resource_management.monitoring_interval_ms !== undefined) loadedConfig.MONITORING_INTERVAL_MS = userSettings.resource_management.monitoring_interval_ms;
        if (userSettings.resource_management.cache_ttl_ms !== undefined) loadedConfig.CACHE_TTL_MS = userSettings.resource_management.cache_ttl_ms;
        if (userSettings.resource_management.max_cache_size !== undefined) loadedConfig.MAX_CACHE_SIZE = userSettings.resource_management.max_cache_size;
      }

      // Load Watcher Settings
      if (userSettings.watcher) {
        if (userSettings.watcher.debounce_ms !== undefined) loadedConfig.WATCHER_DEBOUNCE_MS = userSettings.watcher.debounce_ms;
        if (userSettings.watcher.stability_threshold_ms !== undefined) loadedConfig.WATCHER_STABILITY_THRESHOLD_MS = userSettings.watcher.stability_threshold_ms;
        if (userSettings.watcher.extra_paths) loadedConfig.WATCHER_EXTRA_PATHS = userSettings.watcher.extra_paths;
        if (userSettings.watcher.auto_start !== undefined) {
          loadedConfig.WATCHER_AUTO_START = userSettings.watcher.auto_start;
          loadedConfig.WATCHER.AUTO_START = userSettings.watcher.auto_start;
        }
        if (userSettings.watcher.wipe_mirrored_brain_on_shutdown !== undefined) loadedConfig.WATCHER_WIPE_MIRRORED_BRAIN_ON_SHUTDOWN = userSettings.watcher.wipe_mirrored_brain_on_shutdown;
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
        if (userSettings.database.wipe_on_shutdown !== undefined) loadedConfig.DATABASE.WIPE_ON_SHUTDOWN = userSettings.database.wipe_on_shutdown;
        if (userSettings.database.shared_buffers_mb !== undefined) loadedConfig.DATABASE.SHARED_BUFFERS_MB = userSettings.database.shared_buffers_mb;
        if (userSettings.database.effective_cache_size_mb !== undefined) loadedConfig.DATABASE.EFFECTIVE_CACHE_SIZE_MB = userSettings.database.effective_cache_size_mb;
        if (userSettings.database.work_mem_mb !== undefined) loadedConfig.DATABASE.WORK_MEM_MB = userSettings.database.work_mem_mb;
        if (userSettings.database.maintenance_work_mem_mb !== undefined) loadedConfig.DATABASE.MAINTENANCE_WORK_MEM_MB = userSettings.database.maintenance_work_mem_mb;
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

      // Load Low-Resource Mode Settings (Standard 136)
      if (userSettings.low_resource) {
        if (userSettings.low_resource.enabled !== undefined) loadedConfig.LOW_RESOURCE.ENABLED = userSettings.low_resource.enabled;
        if (userSettings.low_resource.max_recall_low !== undefined) loadedConfig.LOW_RESOURCE.MAX_RECALL_LOW = userSettings.low_resource.max_recall_low;
        if (userSettings.low_resource.max_recall_high !== undefined) loadedConfig.LOW_RESOURCE.MAX_RECALL_HIGH = userSettings.low_resource.max_recall_high;
        if (userSettings.low_resource.max_concurrency !== undefined) loadedConfig.LOW_RESOURCE.MAX_CONCURRENCY = userSettings.low_resource.max_concurrency;
        if (userSettings.low_resource.search_batch_size !== undefined) loadedConfig.LOW_RESOURCE.SEARCH_BATCH_SIZE = userSettings.low_resource.search_batch_size;
        if (userSettings.low_resource.ingest_batch_size !== undefined) loadedConfig.LOW_RESOURCE.INGEST_BATCH_SIZE = userSettings.low_resource.ingest_batch_size;
        if (userSettings.low_resource.vector_ingest_batch !== undefined) loadedConfig.LOW_RESOURCE.VECTOR_INGEST_BATCH = userSettings.low_resource.vector_ingest_batch;
      }

      // Load Ingestion Configuration (Agent-Controlled)
      if (userSettings.ingestion) {
        if (userSettings.ingestion.concept_density) loadedConfig.INGESTION.CONCEPT_DENSITY = userSettings.ingestion.concept_density;
        if (userSettings.ingestion.tag_threshold !== undefined) loadedConfig.INGESTION.TAG_THRESHOLD = userSettings.ingestion.tag_threshold;
        if (userSettings.ingestion.dedup_strength) loadedConfig.INGESTION.DEDUP_STRENGTH = userSettings.ingestion.dedup_strength;
        if (userSettings.ingestion.token_budget_default !== undefined) loadedConfig.INGESTION.TOKEN_BUDGET_DEFAULT = userSettings.ingestion.token_budget_default;
        if (userSettings.ingestion.ingestion_profile) loadedConfig.INGESTION.INGESTION_PROFILE = userSettings.ingestion.ingestion_profile;
      }

      // Load Distiller Configuration (v2.1)
      if (userSettings.distiller) {
        if (userSettings.distiller.similarity_threshold !== undefined) loadedConfig.DISTILLER.SIMILARITY_THRESHOLD = userSettings.distiller.similarity_threshold;
        if (userSettings.distiller.output_format) loadedConfig.DISTILLER.OUTPUT_FORMAT = userSettings.distiller.output_format;
      }

    } catch (e: any) {
      // Check if this is a Zod validation error
      if (e instanceof z.ZodError) {
        console.error('[Config] Invalid configuration in user_settings.json:');
        // ZodError.errors is available in Zod 3.x but not in 4.x
        // In Zod 4.x, use e.flatten() or iterate over issues
        const issues = (e as any).issues || (e as any).flatten?.().errors || [];
        if (issues.length > 0) {
          issues.forEach((err: any) => {
            console.error(`  - ${err.path?.join('.') || 'unknown'}: ${err.message}`);
          });
        }
        console.error('[Config] Please fix the configuration file and restart.');
      } else {
        console.error('[Config] Failed to parse user_settings.json:', e);
      }
    }
  }

  return loadedConfig;
}

// Export configuration
export const config = loadConfig();

export default config;

// Export PATHS for modules that need it
export { PATHS } from './paths.js';