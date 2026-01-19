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

// For __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Define configuration interface
interface Config {
  // Core
  PORT: number;
  HOST: string;
  API_KEY: string;
  LOG_LEVEL: string;
  OVERLAY_PORT: number;

  // Tuning
  DEFAULT_SEARCH_CHAR_LIMIT: number;
  DREAM_INTERVAL_MS: number;
  SIMILARITY_THRESHOLD: number;
  TOKEN_LIMIT: number;
  DREAMER_BATCH_SIZE: number;

  VECTOR_INGEST_BATCH: number;

  // Extrapolated Settings
  WATCHER_DEBOUNCE_MS: number;
  CONTEXT_RELEVANCE_WEIGHT: number;
  CONTEXT_RECENCY_WEIGHT: number;
  DREAMER_CLUSTERING_GAP_MS: number;

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

  // Models
  MODELS: {
    EMBEDDING_DIM: number;
    MAIN: {
      PATH: string;
      CTX_SIZE: number;
      GPU_LAYERS: number;
    };

    ORCHESTRATOR: {
      PATH: string;
      CTX_SIZE: number;
      GPU_LAYERS: number;
    };
    VISION: {
      PATH: string;
      PROJECTOR: string;
      CTX_SIZE: number;
      GPU_LAYERS: number;
    };
  };
}

// Default configuration
const DEFAULT_CONFIG: Config = {
  // Core
  PORT: parseInt(process.env['PORT'] || "3000"),
  HOST: process.env['HOST'] || "0.0.0.0",
  API_KEY: process.env['API_KEY'] || "ece-secret-key",
  LOG_LEVEL: process.env['LOG_LEVEL'] || "INFO",
  OVERLAY_PORT: parseInt(process.env['OVERLAY_PORT'] || "3001"),

  // Tuning
  DEFAULT_SEARCH_CHAR_LIMIT: 524288,
  DREAM_INTERVAL_MS: 3600000, // 60 minutes
  SIMILARITY_THRESHOLD: parseFloat(process.env['SIMILARITY_THRESHOLD'] || "0.8"),
  TOKEN_LIMIT: 1000000,
  DREAMER_BATCH_SIZE: parseInt(process.env['DREAMER_BATCH_SIZE'] || "5"),

  VECTOR_INGEST_BATCH: parseInt(process.env['VECTOR_INGEST_BATCH'] || "500"),

  // Extrapolated Settings
  WATCHER_DEBOUNCE_MS: parseInt(process.env['WATCHER_DEBOUNCE_MS'] || "2000"),
  CONTEXT_RELEVANCE_WEIGHT: parseFloat(process.env['CONTEXT_RELEVANCE_WEIGHT'] || "0.7"),
  CONTEXT_RECENCY_WEIGHT: parseFloat(process.env['CONTEXT_RECENCY_WEIGHT'] || "0.3"),
  DREAMER_CLUSTERING_GAP_MS: parseInt(process.env['DREAMER_CLUSTERING_GAP_MS'] || "900000"), // 15 mins

  // Infrastructure
  REDIS: {
    ENABLED: process.env['REDIS_ENABLED'] === 'true',
    URL: process.env['REDIS_URL'] || "redis://localhost:6379",
    TTL: parseInt(process.env['REDIS_TTL'] || "3600")
  },
  NEO4J: {
    ENABLED: process.env['NEO4J_ENABLED'] === 'true',
    URI: process.env['NEO4J_URI'] || "bolt://localhost:7687",
    USER: process.env['NEO4J_USER'] || "neo4j",
    PASS: process.env['NEO4J_PASSWORD'] || "password"
  },

  // Features
  FEATURES: {
    CONTEXT_STORAGE: process.env['FEATURE_CONTEXT_STORAGE'] === 'true',
    MEMORY_RECALL: process.env['FEATURE_MEMORY_RECALL'] === 'true',
    CODA: process.env['FEATURE_CODA_ENABLED'] === 'true',
    ARCHIVIST: process.env['FEATURE_ARCHIVIST_ENABLED'] === 'true',
    WEAVER: process.env['FEATURE_WEAVER_ENABLED'] === 'true',
    MARKOVIAN: process.env['MARKOVIAN_ENABLED'] === 'true'
  },

  // Models
  MODELS: {
    EMBEDDING_DIM: parseInt(process.env['LLM_EMBEDDING_DIM'] || "768"),
    MAIN: {
      PATH: process.env['LLM_MODEL_PATH'] || "gemma-3-4b-it-abliterated-v2.i1-Q4_K_S.gguf",
      CTX_SIZE: parseInt(process.env['LLM_CTX_SIZE'] || "4096"),
      GPU_LAYERS: parseInt(process.env['LLM_GPU_LAYERS'] || "33")
    },

    ORCHESTRATOR: {
      PATH: process.env['ORCHESTRATOR_MODEL_PATH'] || "Qwen3-4B-Function-Calling-Pro.gguf",
      CTX_SIZE: parseInt(process.env['ORCHESTRATOR_CTX_SIZE'] || "8192"),
      GPU_LAYERS: parseInt(process.env['ORCHESTRATOR_GPU_LAYERS'] || "0")
    },
    VISION: {
      PATH: process.env['VISION_MODEL_PATH'] || "",  // MUST BE SET IN .ENV
      PROJECTOR: process.env['VISION_PROJECTOR_PATH'] || "", // MUST BE SET IN .ENV
      CTX_SIZE: 2048,
      GPU_LAYERS: parseInt(process.env['LLM_GPU_LAYERS'] || "33")
    }
  }
};

// Configuration loader
function loadConfig(): Config {
  // Determine config file path
  const configPath = process.env['SOVEREIGN_CONFIG_PATH'] ||
    path.join(__dirname, '..', '..', 'sovereign.yaml') ||
    path.join(__dirname, '..', 'config', 'default.yaml');

  if (fs.existsSync(configPath)) {
    try {
      const configFile = fs.readFileSync(configPath, 'utf8');
      const parsedConfig = yaml.load(configFile) as Partial<Config>;
      return { ...DEFAULT_CONFIG, ...parsedConfig } as Config;
    } catch (error) {
      console.warn(`Failed to load config from ${configPath}:`, error);
      return DEFAULT_CONFIG;
    }
  }

  return DEFAULT_CONFIG;
}

// Export configuration
export const config = loadConfig();

export default config;