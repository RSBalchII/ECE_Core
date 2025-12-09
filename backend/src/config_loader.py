"""
Configuration Loader for ECE_Core and Anchor

Loads configuration from YAML files with environment variable substitution.
Provides typed configuration objects with validation.
"""
try:
    import yaml
except Exception:
    yaml = None
import os
import re
import logging
from pathlib import Path
from src.utils.config_finder import find_config_path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Configuration loader with environment variable substitution.
    
    Supports ${ENV_VAR} syntax in YAML files.
    Example: password: "${NEO4J_PASSWORD}"
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize config loader.
        
        Args:
            config_path: Path to config.yaml. If None, looks in current directory.
        """
        if config_path is None:
            # Ask the config_finder for the canonical location if present
            candidate = find_config_path()
            if candidate:
                config_path = Path(candidate)
            else:
                # Look for a default in the ece-core directory for backward compatibility
                config_path = Path(__file__).parent.parent / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Dictionary with configuration
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            logger.warning("Using default configuration")
            return {}
        
        try:
            if yaml is None:
                logger.warning("PyYAML not installed; skipping YAML-based config loading")
                return {}
            with open(self.config_path, 'r') as f:
                content = f.read()
            
            # Substitute environment variables
            content = self._substitute_env_vars(content)
            
            # Parse YAML
            config = yaml.safe_load(content)
            
            logger.info(f"Loaded configuration from {self.config_path}")
            self._config = config
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def _substitute_env_vars(self, content: str) -> str:
        """
        Substitute ${ENV_VAR} patterns with environment variable values.
        
        Args:
            content: YAML content with potential ${VAR} patterns
            
        Returns:
            Content with substitutions made
        """
        def replace_env(match):
            env_var = match.group(1)
            value = os.getenv(env_var)
            
            if value is None:
                # Check for default value: ${VAR:-default}
                if ':-' in env_var:
                    var_name, default = env_var.split(':-', 1)
                    value = os.getenv(var_name, default)
                else:
                    logger.warning(f"Environment variable {env_var} not set")
                    # Keep placeholder for optional values
                    return match.group(0)
            
            return value
        
        # Replace ${VAR} and ${VAR:-default}
        pattern = re.compile(r'\$\{([^}]+)\}')
        return pattern.sub(replace_env, content)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.
        
        Args:
            key: Dot-notation key (e.g., "server.port")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        if self._config is None:
            self.load()
        
        if self._config is None:
            return default
        
        # Navigate nested dict with dot notation
        parts = key.split('.')
        value = self._config
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        
        return value
    
    def reload(self) -> Dict[str, Any]:
        """
        Reload configuration from file.
        
        Returns:
            Updated configuration dictionary
        """
        return self.load()
    
    def print_config(self, hide_secrets: bool = True):
        """
        Print current configuration (for debugging).
        
        Args:
            hide_secrets: Whether to hide password fields
        """
        if self._config is None:
            self.load()
        
        config = self._config.copy() if self._config else {}
        
        if hide_secrets:
            # Redact sensitive fields
            config = self._redact_secrets(config)
        
        print("=" * 60)
        print("Current Configuration:")
        print("=" * 60)
        print(yaml.dump(config, default_flow_style=False, sort_keys=False))
        print("=" * 60)
    
    def _redact_secrets(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact sensitive configuration values.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Config with secrets redacted
        """
        redacted = {}
        secret_keys = {'password', 'secret', 'token', 'key', 'api_key'}
        
        for key, value in config.items():
            if isinstance(value, dict):
                redacted[key] = self._redact_secrets(value)
            elif any(secret in key.lower() for secret in secret_keys):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        
        return redacted


# Global config loader instance
_loader: Optional[ConfigLoader] = None


def get_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Get configuration (singleton pattern).
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Configuration dictionary
    """
    global _loader
    
    if _loader is None:
        _loader = ConfigLoader(config_path)
        _loader.load()
    
    return _loader._config or {}


def reload_config() -> Dict[str, Any]:
    """
    Reload configuration from file.
    
    Returns:
        Updated configuration dictionary
    """
    global _loader
    
    if _loader is None:
        return get_config()
    
    return _loader.reload()


def get_value(key: str, default: Any = None) -> Any:
    """
    Get configuration value by key.
    
    Args:
        key: Dot-notation key (e.g., "server.port")
        default: Default value if not found
        
    Returns:
        Configuration value
    """
    global _loader
    
    if _loader is None:
        get_config()
    
    return _loader.get(key, default) if _loader else default
