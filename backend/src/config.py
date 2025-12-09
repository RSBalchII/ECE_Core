"""
Comprehensive configuration management for ECE_Core.
Organized by component/file for easy maintenance.
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, model_validator
from pathlib import Path
try:
    import yaml
except Exception:
    yaml = None
from dotenv import load_dotenv
from typing import Optional
import json
from urllib.parse import urlparse
import os

try:
    from importlib.metadata import version as _get_pkg_version
    try:
        _pkg_version = _get_pkg_version("ece-core")
    except Exception:
        _pkg_version = None
except Exception:
    _pkg_version = None

class Settings(BaseSettings):
    """
    Configuration organized by component.
    All settings can be overridden via environment variables or .env file.
    """
    
    # ============================================================
    # LLM_CLIENT.PY - Local GGUF Model Settings
    # ============================================================
    llm_api_base: str = "http://localhost:8080/v1"  # llama.cpp server
    # Optional: specify a distinct base URL for embeddings (useful when embedding server runs separately on port 8081)
    llm_embeddings_api_base: Optional[str] = "http://127.0.0.1:8081/v1"
    # Optional: specific model name for embeddings (embedding-capable model like qwen3-embedding-4b)
    llm_embeddings_model_name: Optional[str] = ""
    # Control whether a local GGUF model should be used as a fallback for embeddings
    llm_embeddings_local_fallback_enabled: bool = False
    # Embeddings chunk tuning
    llm_embeddings_chunk_size_default: int = 2048  # default char-based chunk size for long docs (reduced to avoid embedding server 500s)
    llm_embeddings_min_chunk_size: int = 128  # smallest allowed chunk size
    # Sequence of backoff chunk sizes to try when server reports input too large
    llm_embeddings_chunk_backoff_sequence: list[int] = [2048, 1024, 512, 256, 128]
    # Enable adaptive backoff for embeddings (parse server messages and try smaller chunk sizes automatically)
    llm_embeddings_adaptive_backoff_enabled: bool = True
    # Default batch size (number of documents per embeddings API request). Lower default to avoid server overloads.
    llm_embeddings_default_batch_size: int = 2
    # Model selection (name/path used by the LLM client and helper script)
    # Default production-tuned LLM settings for OpenAI-20B on 16GB RTX 4090
    llm_model_name: str = "OpenAI-20B-NEOPlus-Uncensored-IQ4_NL.gguf"  # Model name/path used by launcher
    llm_model_path: str = ""  # Optional local model path (GGUF) — leave blank to avoid loading if not present
    # Optimized for 16GB RTX 4090 with 64k context window to maximize memory utilization
    # 64k context results in ~8GB KV cache which fits comfortably with model weight on RTX 4090
    llm_context_size: int = 65536  # OpenAI-20B-NEOPlus IQ4_NL - 64k context window (synchronized with hardware capabilities)
    # Tuned to keep responses snappy while avoiding large GPU occupancy
    llm_max_tokens: int = 4096  # Increased generation length for long reasoning chains
    llm_temperature: float = 1.0  # Reka default: higher temperature to support novel reasoning
    llm_top_p: float = 0.95  # Nucleus sampling threshold tuned for Reka
    llm_timeout: int = 300  # Request timeout seconds
    # Offload all layers to GPU for maximum inference speed on RTX 4090
    llm_gpu_layers: int = -1  # Use -1 to pin all layers to GPU (where supported)
    llm_threads: int = 12  # CPU threads
    llm_concurrency: int = 4  # How many concurrent LLM calls to allow
    llm_local_embeddings: bool = True  # Load local model with embeddings enabled when used as fallback
    # Character->token heuristics for chunk sizing; tokens ~ 4 chars, useful for server token limits
    llm_chars_per_token: int = 4
    # Fraction of server context to use for chunking (e.g., 0.5 = use half of the model context for chunk size)
    llm_chunk_context_ratio: float = 0.5
    # Stop tokens configuration for Reka model
    llm_stop_tokens: Optional[list] = ["< sep >", ""]  # Added Reka stop token
    # Chat template configuration - specify which template to use for formatting conversations
    llm_chat_template: str = "openai"  # Changed from qwen3-thinking to openai for simpler, more predictable tool handling
    # Batch size optimizations for 16GB VRAM to maximize context window
    llm_batch_size: int = 1024  # Optimized to conserve VRAM/RAM during processing
    llm_ubatch_size: int = 1024 # Optimized to conserve VRAM/RAM during processing

    @property
    def resolved_chat_template(self) -> str:
        """Auto-detect chat template based on model name if set to 'auto'"""
        if self.llm_chat_template.lower() == 'auto':
            model_name = getattr(self, 'llm_model_name', '').lower()
            if 'gemma' in model_name:
                return 'gemma3'
            elif 'qwen' in model_name:
                return 'qwen3-thinking'
            elif 'llama' in model_name or 'llm' in model_name:
                # Llama models usually use standard chatml format
                return 'openai'  # Using openai format as standard for Llama
            elif 'moe' in model_name or '4x' in model_name or 'california' in model_name:
                # For your specific MoE model, use standard format since it's llama3.2 based
                return 'openai'  # Llama3.2 based models use standard chat format
            else:
                return 'openai'  # Default fallback
        return self.llm_chat_template
    # (duplicate 'llm_chars_per_token' removed)

    # ============================================================
    # LLAMA.CPP SERVER & EMBEDDING SERVER RUNTIME CONFIG
    # Path to the built llama-server executable (explicit path overrides auto-detection)
    llama_server_exe_path: Optional[str] = None
    # Default ports for API and embedding servers
    llama_server_default_port: int = 8080
    llama_embed_server_default_port: int = 8081
    # Allow interactive model selection via `select_model.py` if model not configured in settings
    llama_allow_select_model: bool = True
    # Additional server runtime tuning flags exposed for convenience
    llama_server_cont_batching: bool = True
    llama_server_flash_attn: str = "auto"
    llama_server_cache_type_k: str = "f16"
    llama_server_cache_type_v: str = "f16"
    llama_server_repeat_penalty: float = 1.1
    # llama.cpp server batch tuning
    # Batch tuning: set a larger logical batch size to allow batching while keeping micro batches small
    # Defaults tuned for RTX 4090 16GB VRAM: large logical batch, small ubatch to avoid VRAM spikes
    llama_server_batch_size: int = 2048  # logical max batch size (llama-server --batch-size)
    llama_server_ubatch_size: int = 2048  # physical ubatch size (llama-server --ubatch-size) - raised for RTX 4090 stability
    llama_server_parallel: int = 1  # number of parallel sequences/slots (llama-server --parallel)
    # Optional cap for UBATCH to avoid allocating more memory than GPU can handle
    llama_server_ubatch_max: Optional[int] = None
    # Optional: configure prompt cache ram in MiB; default 0 disables prompt cache (good for VRAM-constrained setups)
    llama_cache_ram: int = 0
    # Optional stop tokens to instruct the model to terminate completions
    llm_stop_tokens: Optional[list[str]] = None
    
    # ============================================================
    # MEMORY.PY - Tiered Memory Settings
    # ============================================================
    # Redis (Hot/Working Memory)
    redis_url: str = "redis://localhost:6379"
    redis_ttl: int = 3600  # Session TTL in seconds
    redis_max_tokens: int = 32000  # Max tokens in Redis before flush (increased from 16000 for larger buffer)
    
    # Memory thresholds
    max_context_tokens: int = 60000  # Max tokens in total context (synchronized with 64k hardware window, leaving 5k buffer for output)
    summarize_threshold: int = 48000  # Trigger summarization when Redis exceeds this (allowing much longer conversations before forcing rotation)
    
    # ============================================================
    # CONTEXT_MANAGER.PY - Context Assembly
    # ============================================================
    # Archivist settings (summarization)
    archivist_enabled: bool = True
    archivist_chunk_size: int = 8000  # Tokens per chunk for summarization (increased to preserve more detail with 64k context)
    archivist_overlap: int = 500  # Overlap between chunks (increased for better continuity with larger chunks)
    archivist_compression_ratio: float = 0.5  # Target 50% of original size (reduced aggressiveness from 0.3)
    
    # Context tiers
    context_recent_turns: int = 50  # Recent conversation turns to include (increased from 10 to support 50+ exchanges)
    context_summary_limit: int = 20  # Max historical summaries to include (increased from 8)
    context_entity_limit: int = 50  # Max entity-based memories (increased from 15)

    # Defaults for memory provenance & freshness
    memory_default_provenance_score: float = 0.5  # Default provenance when metadata is unknown (0.0-1.0)
    memory_default_freshness_score: float = 1.0  # Freshness score at creation (1.0 = brand new)
    # Distiller caching settings
    memory_distill_cache_enabled: bool = True
    memory_distill_cache_ttl: int = 86400  # in seconds

    # ============================================================
    # ARCHIVIST - Auto-Purge (Janitor) Settings
    # ============================================================
    # When enabled, Archivist will periodically scan for and optionally delete
    # contaminated memory nodes that match the configured markers.
    archivist_auto_purge_enabled: bool = False
    archivist_auto_purge_interval_seconds: int = 600  # default 10 minutes
    archivist_auto_purge_dry_run: bool = True  # default to dry-run to avoid accidental deletes
    # A set of markers used to detect contaminated nodes. Lower-cased.
    archivist_auto_purge_markers: list[str] = [
        "thinking_content",
        "combined_text",
        "prompt-logs",
        "prompt_logs",
        "calibration_run",
        "dry-run",
        "dry_run",
        "[planner]",
        "--- start of file:",
        "(anchor) ps ",
        "[info] http",
        '"thinking_content":'
    ]
    
    # ============================================================
    # QLEARNING_RETRIEVER.PY - Graph Retrieval
    # ============================================================
    qlearning_enabled: bool = True
    qlearning_learning_rate: float = 0.1
    qlearning_discount_factor: float = 0.9
    qlearning_epsilon: float = 0.3  # Exploration rate
    qlearning_max_hops: int = 3  # Graph traversal depth
    qlearning_max_paths: int = 5  # Max paths to explore
    qlearning_save_interval: int = 10  # Save Q-table every N queries
    qlearning_table_path: str = "./q_table.json"
    
    # ============================================================
    # EXTRACT_ENTITIES.PY - Entity Extraction
    # ============================================================
    entity_extraction_batch_size: int = 20  # Process N turns at a time
    entity_extraction_delay: float = 0.1  # Delay between LLM calls (rate limiting)
    entity_min_confidence: float = 0.5  # Min confidence for entity extraction
    entity_types: list[str] = ["PERSON", "CONCEPT", "PROJECT", "CONDITION", "SKILL"]  # Specify entity types explicitly
    
    # ============================================================
    # NEO4J - Knowledge Graph (Optional)
    # ============================================================
    neo4j_enabled: bool = True  # Enable Neo4j for memory storage and retrieval
    neo4j_uri: str = "bolt://localhost:7687"  # Neo4j connection URI
    neo4j_user: str = "neo4j"  # Neo4j username
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")  # Neo4j password from environment variable
    neo4j_max_connection_pool_size: int = 50  # Max connection pool size
    neo4j_connection_timeout: int = 30  # Connection timeout in seconds
    # ============================================================
    # NEO4J RECONNECT (resilience settings for critical DB errors)
    # If Neo4j has a critical error at startup, attempt to reconnect in background.
    neo4j_reconnect_enabled: bool = True
    neo4j_reconnect_initial_delay: int = 5  # seconds before first reconnect attempt
    neo4j_reconnect_max_attempts: int = 6  # attempts before stopping
    neo4j_reconnect_backoff_factor: float = 2.0  # exponential backoff multiplier

    # ============================================================
    # VECTOR DB (Optional)
    # ============================================================
    vector_enabled: bool = False  # Enable vector DB usage for semantic search
    vector_adapter_name: str = "redis"  # Name of adapter to use (redis, faiss, pinecone)
    vector_auto_embed: bool = False  # Autogenerate embeddings for new memories (via llm_client)
    
    # ============================================================
    # MAIN.PY - ECE Server
    # ============================================================
    ece_host: str = "127.0.0.1"
    ece_port: int = 8000
    ece_log_level: str = "INFO"
    # Optional full URL form for MCP server (e.g., http://localhost:8008)
    mcp_url: Optional[str] = None
    # Versioning
    # Detect the package version if installed; otherwise allow ECE_VERSION env var or fallback to 'dev'
    ece_version: str = os.getenv('ECE_VERSION', _pkg_version or 'dev')
    ece_cors_origins: list[str] = ["*"]  # CORS allowed origins
    
    # ============================================================
    # SECURITY - API Authentication
    # ============================================================
    ece_api_key: Optional[str] = None
    ece_require_auth: bool = False
    # ------------------------------------------------------------------
    # MCP Server configuration
    # ------------------------------------------------------------------
    mcp_enabled: bool = False
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8421
    # Optional: support YAML `server.host` / `server.port` semantics via SERVER_HOST / SERVER_PORT env vars
    server_host: Optional[str] = None
    server_port: Optional[int] = None
    # Per-protocol API key for MCP (if required). Fallback to ece_api_key if not set.
    mcp_api_key: Optional[str] = None
    
    # ============================================================
    # SECURITY - Audit Logging
    # ============================================================
    audit_log_enabled: bool = True
    audit_log_path: str = "./logs/audit.log"
    audit_log_tool_calls: bool = True
    audit_log_memory_access: bool = False
    
    # ============================================================
    # ANCHOR - CLI Client
    # ============================================================
    anchor_session_id: str = "anchor-session"
    anchor_timeout: int = 300
    
    # ============================================================
    # GRAPH_REASONER.PY - Graph-R1 Reasoning
    # ============================================================
    reasoning_max_iterations: int = 5  # Markovian thinking iterations
    reasoning_enabled: bool = True
    # ============================================================
    # TOOL EXECUTION - Maximum iterations when processing tool calls
    # This controls how many tool-execute/regenerate cycles are allowed
    # Default kept in sync with ToolExecutor default (3)
    # New recommended setting name: tool_max_iterations (for non-MCP generic use)
    tool_max_iterations: int = 3
    # Backward compatibility: keep the old MCP-prefixed name in place
    mcp_max_tool_iterations: int = 3
    
    # ============================================================
    # Computed Properties
    # ============================================================
    @property
    def archivist_max_summary_tokens(self) -> int:
        """Target summary size based on compression ratio"""
        return int(self.summarize_threshold * self.archivist_compression_ratio)
    
    @property
    def llm_model(self) -> str:
        """Model name for API calls (backward compatibility)"""
        return self.llm_model_name
    
    # ============================================================
    # Pydantic Config
    # ============================================================
    # Pydantic v2 model config: ignore extra environment variables to avoid validation errors
    model_config = ConfigDict(extra="ignore", env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @model_validator(mode='after')
    def _post_init(self):
        """After validation, derive host/port settings from URL fields if present.

        This allows the YAML config to specify `mcp: { url: "http://localhost:8008" }` and
        `server: { host: "0.0.0.0", port: 8000 }` while preserving backward-compatible
        `mcp_host`/`mcp_port` and `ece_host`/`ece_port` fields.
        """
        # Parse mcp_url if present
        if getattr(self, 'mcp_url', None):
            try:
                parsed = urlparse(self.mcp_url)
                if parsed.hostname:
                    object.__setattr__(self, 'mcp_host', parsed.hostname)
                if parsed.port:
                    object.__setattr__(self, 'mcp_port', parsed.port)
            except Exception:
                pass

        # Apply server_host/server_port to ece_host/ece_port if provided
        if getattr(self, 'server_host', None):
            object.__setattr__(self, 'ece_host', self.server_host)
        if getattr(self, 'server_port', None):
            try:
                object.__setattr__(self, 'ece_port', int(self.server_port))
            except Exception:
                pass

        # Parse possible stringified list for llm_stop_tokens from environment/YAML fallback.
        try:
            val = getattr(self, 'llm_stop_tokens', None)
            if isinstance(val, str):
                s = val.strip()
                if s.startswith('[') and s.endswith(']'):
                    try:
                        # Convert single quotes to double quotes if needed, then parse JSON
                        j = s.replace("'", '"')
                        parsed = json.loads(j)
                        if isinstance(parsed, list):
                            object.__setattr__(self, 'llm_stop_tokens', parsed)
                    except Exception:
                        # Fall through to comma-splitting
                        items = [i.strip() for i in s.strip('[]').split(',') if i.strip()]
                        object.__setattr__(self, 'llm_stop_tokens', items)
                else:
                    # Comma-separated values
                    items = [i.strip() for i in s.split(',') if i.strip()]
                    object.__setattr__(self, 'llm_stop_tokens', items)
        except Exception:
            pass

        return self

    # ============================================================
    # MEMORY WEAVER (AUTONOMOUS REPAIR)
    # ============================================================
    weaver_enabled: bool = True
    # We recommend enabling real commits after a short observation period
    # for production readiness; default to enabled for Sovereign Brain mode.
    weaver_dry_run_default: bool = False
    weaver_threshold: float = 0.55
    weaver_delta: float = 0.05
    weaver_time_window_hours: int = 24
    weaver_max_commit: int = 50
    weaver_prefer_same_app: bool = True
    weaver_commit_enabled: bool = True
    # When present, nodes containing this tag in m.tags will be excluded from weaver runs
    weaver_exclude_tag: Optional[str] = '#corrupted'
    # Defaults related to weaver and repair scripts
    weaver_candidate_limit: int = 200  # candidate limit per summary in repair runs
    weaver_batch_size_default: int = 2  # default batch size used by repair/weaver when not overridden
    # Backwards compatible alias and convenience env name (WEAVER_BATCH_SIZE)
    # If set, this value takes precedence over `weaver_batch_size_default`.
    weaver_batch_size: int | None = None
    # Sleep seconds to wait between batches for safe GPU breathing room
    weaver_sleep_between_batches: float = 1.0

    # Matrix / Factory Configuration - spawn worker processes for heavy async tasks
    matrix_worker_count: int = 8  # Number of worker processes for Matrix/Weaver tasks

# Global settings instance
def _load_config_fallbacks() -> None:
    """Load configs from the recommended `configs/` directory and .env files.

    Behavior:
    - Loads configs/config.yaml if present, flattening keys into environment variables
      so that Pydantic BaseSettings picks them up.`
    - Loads .env from `configs/.env` if present, else root `.env`.
    - Does not override existing environment variables.
    """
    repo_root = Path(__file__).resolve().parents[1]
    configs_dir = repo_root / "configs"
    # 1) Load .env file from config dir if present (otherwise root .env). Don't override existing env vars.
    candidate_envs = [configs_dir / ".env", repo_root / ".env"]
    for envf in candidate_envs:
        if envf.exists():
            try:
                load_dotenv(dotenv_path=str(envf), override=False)
            except Exception:
                pass
            break
    # 2) Load YAML defaults and set environment variables for missing keys
    if yaml is None:
        # PyYAML not installed; skip YAML defaults. If a YAML config exists, print a helpful hint.
        repo_root = Path(__file__).resolve().parents[1]
        configs_dir = repo_root / "configs"
        candidates = [configs_dir / "config.yaml", repo_root / "config.yaml", repo_root / "ece-core" / "config.yaml"]
        config_yaml = next((p for p in candidates if p.exists()), None)
        if config_yaml is not None:
            try:
                print(f"⚠️  PyYAML is not installed; found YAML config at {config_yaml}. Install PyYAML (pip install PyYAML) to load YAML-based defaults.")
            except Exception:
                # If printing fails in constrained env, just pass
                pass
        return
    # Support multiple locations for config.yaml to preserve compatibility with existing scripts
    candidates = [configs_dir / "config.yaml", repo_root / "config.yaml", repo_root / "ece-core" / "config.yaml"]
    config_yaml = next((p for p in candidates if p.exists()), None)
    if config_yaml is not None:
        try:
            raw = yaml.safe_load(config_yaml.read_text()) or {}
        except Exception:
            raw = {}
        def _flatten(cfg: dict, prefix: str = None):
            for k, v in (cfg or {}).items():
                key = f"{(prefix + '_') if prefix else ''}{k}".upper()
                if isinstance(v, dict):
                    yield from _flatten(v, key)
                else:
                    yield key, v
        for ek, ev in _flatten(raw):
            # Only set env var if not already present
            if os.environ.get(ek) is None and ev is not None:
                os.environ[ek] = str(ev)

_load_config_fallbacks()

try:
    settings = Settings()
except Exception:
    # During tests or in constrained environments, extra env vars can cause validation errors.
    # Fall back to a constructed default settings object to avoid blocking collection.
    settings = Settings.construct()

# Legacy exports for backward compatibility
