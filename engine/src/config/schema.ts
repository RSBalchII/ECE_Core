/**
 * Configuration Schema Validation using Zod
 *
 * Provides runtime validation for all configuration values
 * with clear error messages for invalid configurations.
 */

import { z } from 'zod';

// Infrastructure schemas
const RedisSchema = z.object({
  ENABLED: z.boolean().default(false),
  URL: z.string().url().default('redis://localhost:6379'),
  TTL: z.number().int().positive().default(3600)
});

const Neo4jSchema = z.object({
  ENABLED: z.boolean().default(false),
  URI: z.string().url().default('bolt://localhost:7687'),
  USER: z.string().default('neo4j'),
  PASS: z.string().default('password')
});

// Feature flags schema
const FeaturesSchema = z.object({
  CONTEXT_STORAGE: z.boolean().default(true),
  MEMORY_RECALL: z.boolean().default(true),
  CODA: z.boolean().default(true),
  ARCHIVIST: z.boolean().default(true),
  WEAVER: z.boolean().default(true),
  MARKOVIAN: z.boolean().default(true)
});

// Model configuration schemas
const ModelConfigSchema = z.object({
  PATH: z.string(),
  CTX_SIZE: z.number().int().positive().default(8192),
  GPU_LAYERS: z.number().int().min(0).default(0),
  MAX_TOKENS: z.number().int().positive().default(1024)
});

const VisionModelSchema = ModelConfigSchema.extend({
  PROJECTOR: z.string().default('')
});

const ModelsSchema = z.object({
  EMBEDDING_DIM: z.number().int().positive().default(768),
  MAIN: ModelConfigSchema,
  ORCHESTRATOR: ModelConfigSchema,
  VISION: VisionModelSchema
});

// Services schema
const ServicesSchema = z.object({
  VISION_SERVER_PORT: z.number().int().min(1).max(65535).default(8081),
  CHAT_SERVER_PORT: z.number().int().min(1).max(65535).default(8080),
  TAG_INFECTOR_UNLOAD_TIMEOUT: z.number().int().positive().default(300000),
  TAG_GLINER_CHECK_INTERVAL: z.number().int().positive().default(60000)
});

// Search configuration schema
const SearchSchema = z.object({
  strategy: z.enum(['hybrid', 'standard', 'max-recall']).default('hybrid'),
  hide_years_in_tags: z.boolean().default(true),
  whitelist: z.array(z.string()).default([]),
  max_chars_default: z.number().int().positive().default(524288),
  max_chars_limit: z.number().int().positive().default(20000),
  fts_window_size: z.number().int().positive().default(1500),
  fts_padding: z.number().int().positive().default(750)
});

// Limits schema
const LimitsSchema = z.object({
  MAX_FILE_SIZE_BYTES: z.number().int().positive().default(10485760),
  MAX_CONTENT_LENGTH_CHARS: z.number().int().positive().default(5000),
  MAX_CHUNK_SIZE_CHARS: z.number().int().positive().default(3000),
  MAX_SUMMARY_LENGTH_CHARS: z.number().int().positive().default(2000),
  DATE_EXTRACTOR_SCAN_LIMIT: z.number().int().positive().default(2000)
});

// Database schema
const DatabaseSchema = z.object({
  WIPE_ON_STARTUP: z.boolean().default(true)
});

// Adaptive Concurrency schema (Standard 132)
const AdaptiveConcurrencySchema = z.object({
  SEQUENTIAL_THRESHOLD_MB: z.number().int().positive().default(2048),
  PARALLEL_THRESHOLD_MB: z.number().int().positive().default(8192),
  MAX_CONCURRENCY: z.number().int().positive().default(5),
  LOW_MEMORY_BATCH_SIZE: z.number().int().positive().default(1),
  HIGH_MEMORY_BATCH_SIZE: z.number().int().positive().default(20),
  FORCE_SEQUENTIAL: z.boolean().default(false),
  FORCE_PARALLEL: z.boolean().default(false)
});

// Memory Management schema (Standards 127/134/135)
const MemorySchema = z.object({
  HEAP_PRESSURE_MB: z.number().int().positive().default(500),
  THROTTLE_START_MB: z.number().int().positive().default(800),
  THROTTLE_MAX_MB: z.number().int().positive().default(1200),
  EMERGENCY_STOP_MB: z.number().int().positive().default(1500),
  SEARCH_RESULTS_BATCH_SIZE: z.number().int().positive().default(20),
  ENABLE_STREAMING_RESULTS: z.boolean().default(false)
});

// LLM Provider schema
const LlmProviderSchema = z.object({
  provider: z.enum(['local', 'remote']).default('local'),
  remote_url: z.string().url().optional(),
  remote_model: z.string().optional(),
  model_dir: z.string().default('./models'),
  chat_model: z.string(),
  task_model: z.string(),
  gpu_layers: z.number().int().min(0).default(0),
  ctx_size: z.number().int().positive().default(8192),
  max_tokens: z.number().int().positive().default(1024),
  orchestrator_ctx_size: z.number().int().positive().default(8192),
  orchestrator_gpu_layers: z.number().int().min(0).default(0),
  orchestrator_max_tokens: z.number().int().positive().default(2048),
  vision_model: z.string().default(''),
  vision_projector: z.string().default(''),
  vision_ctx_size: z.number().int().positive().default(2048),
  vision_gpu_layers: z.number().int().min(0).default(11),
  vision_max_tokens: z.number().int().positive().default(1024)
});

// Server schema
const ServerSchema = z.object({
  host: z.string().regex(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/, 'Invalid IP address').default('0.0.0.0'),
  port: z.number().int().min(1).max(65535).default(3160),
  api_key: z.string().optional()
});

// Resource Management schema
const ResourceManagementSchema = z.object({
  gc_cooldown_ms: z.number().int().positive().default(30000),
  max_atoms_in_memory: z.number().int().positive().default(2000),
  monitoring_interval_ms: z.number().int().positive().default(30000)
});

// Watcher schema
const WatcherSchema = z.object({
  debounce_ms: z.number().int().positive().default(2000),
  stability_threshold_ms: z.number().int().positive().default(2000),
  extra_paths: z.array(z.string()).default([])
});

// Context schema
const ContextSchema = z.object({
  relevance_weight: z.number().min(0).max(1).default(0.7),
  recency_weight: z.number().min(0).max(1).default(0.3),
  clustering_gap_ms: z.number().int().positive().optional()
});

// Physics schema
const PhysicsSchema = z.object({
  damping_factor: z.number().min(0).max(1).default(0.85),
  time_decay_lambda: z.number().positive().default(0.00001),
  temperature: z.number().min(0).max(1).default(0.2),
  gravity_threshold: z.number().positive().default(0.01),
  walk_radius: z.number().int().positive().default(1),
  max_per_hop: z.number().int().positive().default(50),
  direct_limit: z.number().int().positive().default(5),
  walker_limit: z.number().int().positive().default(10)
});

// Tagging schema
const TaggingSchema = z.object({
  modulation_level: z.number().int().min(0).max(100).default(50),
  atom_as_tag: z.boolean().default(false),
  strict_atom_selection: z.boolean().default(true),
  entity_extraction: z.object({
    enabled: z.boolean().default(true),
    min_confidence: z.number().min(0).max(1).default(0.6),
    categories: z.array(z.string()).default(['PERSON', 'ORG', 'PRODUCT', 'EVENT', 'LOCATION'])
  }),
  blacklist_strictness: z.number().int().min(0).max(100).default(75),
  common_words_filter: z.boolean().default(true),
  min_tag_length: z.number().int().positive().default(3),
  max_tags_per_molecule: z.number().int().positive().default(20)
});

// MCP schema
const McpSchema = z.object({
  enabled: z.boolean().default(true),
  require_api_key: z.boolean().default(true),
  api_key: z.string().optional(),
  rate_limit_requests_per_minute: z.number().int().positive().default(60),
  max_query_results: z.number().int().positive().default(50),
  restrict_to_localhost: z.boolean().default(true),
  allowed_operations: z.array(z.string()).default(['query', 'read_file', 'get_stats']),
  blocked_operations: z.array(z.string()).default([])
});

// Main configuration schema
export const ConfigSchema = z.object({
  // Core
  PORT: z.number().int().min(1).max(65535).default(3160),
  HOST: z.string().regex(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/, 'Invalid IP address').default('0.0.0.0'),
  API_KEY: z.string().default(''),
  LOG_LEVEL: z.enum(['DEBUG', 'INFO', 'WARN', 'ERROR']).default('INFO'),
  OVERLAY_PORT: z.number().int().min(1).max(65535).default(3002),

  // LLM Provider
  LLM_PROVIDER: z.enum(['local', 'remote']).default('local'),
  REMOTE_LLM_URL: z.string().url().default('http://localhost:8000/v1'),
  REMOTE_MODEL_NAME: z.string().default('default'),
  LLM_MODEL_DIR: z.string().default('models'),

  // Tuning
  DEFAULT_SEARCH_CHAR_LIMIT: z.number().int().positive().default(524288),
  SIMILARITY_THRESHOLD: z.number().min(0).max(1).default(0.8),
  TOKEN_LIMIT: z.number().int().positive().default(1000000),
  VECTOR_INGEST_BATCH: z.number().int().positive().default(50),

  // Context Relevance
  CONTEXT_RELEVANCE_WEIGHT: z.number().min(0).max(1).default(0.7),
  CONTEXT_RECENCY_WEIGHT: z.number().min(0).max(1).default(0.3),

  // Infrastructure
  REDIS: RedisSchema,
  NEO4J: Neo4jSchema,

  // Features
  FEATURES: FeaturesSchema,

  // Search
  SEARCH: SearchSchema,

  // Models
  MODELS: ModelsSchema,

  // Services
  SERVICES: ServicesSchema,

  // Limits
  LIMITS: LimitsSchema,

  // Database
  DATABASE: DatabaseSchema,

  // Adaptive Concurrency
  ADAPTIVE_CONCURRENCY: AdaptiveConcurrencySchema,

  // Memory Management
  MEMORY: MemorySchema
});

// User settings schema (for user_settings.json)
export const UserSettingsSchema = z.object({
  server: ServerSchema.optional(),
  llm: LlmProviderSchema.optional(),
  search: SearchSchema.partial().optional(),
  resource_management: ResourceManagementSchema.optional(),
  watcher: WatcherSchema.optional(),
  context: ContextSchema.optional(),
  services: ServicesSchema.optional(),
  limits: LimitsSchema.partial().optional(),
  database: DatabaseSchema.partial().optional(),
  adaptive_concurrency: AdaptiveConcurrencySchema.partial().optional(),
  memory: MemorySchema.partial().optional(),
  physics: PhysicsSchema.optional(),
  tagging: TaggingSchema.optional(),
  mcp: McpSchema.optional(),
  user: z.object({
    name: z.string().optional(),
    current_state: z.string().optional()
  }).optional(),
  dreamer: z.object({
    enabled: z.boolean().default(true),
    schedule: z.string().default('0 3 * * *')
  }).optional()
});

// Type exports
export type Config = z.infer<typeof ConfigSchema>;
export type UserSettings = z.infer<typeof UserSettingsSchema>;

/**
 * Validate and parse user settings
 * @throws {z.ZodError} if validation fails
 */
export function validateUserSettings(settings: unknown): UserSettings {
  return UserSettingsSchema.parse(settings);
}

/**
 * Validate and parse configuration
 * @throws {z.ZodError} if validation fails
 */
export function validateConfig(config: unknown): Config {
  return ConfigSchema.parse(config);
}

/**
 * Safe validation that returns errors instead of throwing
 */
export function safeValidateConfig(config: unknown): { success: boolean; data?: Config; error?: z.ZodError } {
  const result = ConfigSchema.safeParse(config);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return { success: false, error: result.error };
}
