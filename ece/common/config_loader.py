"""
Configuration loader module for the External Context Engine (ECE)
This module provides a convenience interface to the ConfigManager
with additional helper methods and environment variable support.
"""

import os
from typing import Any, Dict, Optional
from .config_manager import ConfigManager


class Config:
    """
    Configuration class that acts as a wrapper around ConfigManager
    to provide convenient methods for accessing common settings.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration loader
        :param config_path: Path to the config file to use as fallback
        """
        self.config_manager = ConfigManager(config_path=config_path)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot-notation path.
        This now uses the updated ConfigManager which supports environment variables.
        :param key_path: Dot-separated path to the config value (e.g. "llm.active_provider")
        :param default: Default value if not found
        :return: Configuration value
        """
        return self.config_manager.get(key_path, default)

    def get_active_provider(self) -> str:
        """Get the active LLM provider"""
        return self.get("llm.active_provider", "llama_cpp")

    def get_llm_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for a specific LLM provider"""
        default_config = {}
        provider_config = self.get(f"llm.providers.{provider}", default_config)

        # Override with environment variables specific to the provider
        if provider == "llama_cpp":
            if os.getenv("LLM_LLAMA_CPP_MODEL_PATH"):
                provider_config["model_path"] = os.getenv("LLM_LLAMA_CPP_MODEL_PATH")
            if os.getenv("LLM_LLAMA_CPP_API_BASE"):
                provider_config["api_base"] = os.getenv("LLM_LLAMA_CPP_API_BASE")
            if os.getenv("LLM_LLAMA_CPP_MODEL"):
                provider_config["model"] = os.getenv("LLM_LLAMA_CPP_MODEL")

        return provider_config

    def get_redis_url(self) -> str:
        """Get Redis URL"""
        return os.getenv(
            "REDIS_URL", self.get("cache.redis_url", "redis://localhost:6379")
        )

    def get_neo4j_config(self) -> Dict[str, str]:
        """Get Neo4j configuration"""
        return {
            "uri": os.getenv(
                "NEO4J_URI", self.get("neo4j.uri", "bolt://localhost:7687")
            ),
            "user": os.getenv("NEO4J_USER", self.get("neo4j.user", "neo4j")),
            "password": os.getenv(
                "NEO4J_PASSWORD", self.get("neo4j.password", "password")
            ),
        }

    def get_memory_limit(self) -> int:
        """Get memory limit in MB"""
        return int(
            os.getenv(
                "MEMORY_LIMIT_MB",
                str(self.get("system.resources.memory_limit_mb", 2048)),
            )
        )

    def get_debug_verbose_output(self) -> bool:
        """Get debug verbose output setting"""
        verbose_env = os.getenv("DEBUG_VERBOSE_OUTPUT", "").lower()
        if verbose_env in ["true", "1", "yes", "on"]:
            return True
        elif verbose_env in ["false", "0", "no", "off"]:
            return False
        else:
            # Fall back to config file
            return self.get("debug.verbose_output", False)


# Singleton instance for global access
_config_instance = None


def get_config() -> Config:
    """
    Get the global configuration instance
    :return: Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
