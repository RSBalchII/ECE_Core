"""
Centralized configuration management for the External Context Engine (ECE).

This module provides unified configuration handling across all ECE components,
with support for loading, updating, validating, and versioning configuration files.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from copy import deepcopy
import datetime

from .project_root import get_project_root, get_config_path


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class ConfigManager:
    """Centralized configuration management for ECE system."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        auto_load: bool = True,
        version_check: bool = True,
    ):
        """
        Initialize the ConfigManager.

        Args:
            config_path: Path to the config file, defaults to auto-detection
            auto_load: Whether to automatically load the config on initialization
            version_check: Whether to check and update config version on load
        """
        self._config_path = config_path or get_config_path()
        self._config = {}
        self._original_config = {}
        self._version_check = version_check

        if auto_load:
            self.load()

        # Setup logger
        self.logger = logging.getLogger(__name__)

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.

        Returns:
            Dictionary containing the loaded configuration
        """
        if not self._config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self._config_path}")

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

            # Store original config for potential rollback
            self._original_config = deepcopy(self._config)

            # Check and update config version if needed
            if self._version_check:
                self._ensure_config_version()

            return self._config
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"Invalid YAML in config file: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Error loading config file: {e}")

    def _ensure_config_version(self):
        """Ensure the configuration has the correct version and update if necessary."""
        current_version = self._config.get("version", "1.0.0")

        # If no version is set, initialize with the current version
        if not self._config.get("version"):
            self._config["version"] = "2.0.0"
            self._config["version_updated"] = datetime.datetime.now().isoformat()
            # Use safe logging in case logger is not initialized yet
            try:
                self.logger.info(
                    f"Initialized configuration version to {self._config['version']}"
                )
            except AttributeError:
                import logging

                logger = logging.getLogger(__name__)
                logger.info(
                    f"Initialized configuration version to {self._config['version']}"
                )

        # Add any schema migrations here as needed
        # Example migration for future versions:
        # if current_version < '2.0.0':
        #     self._migrate_to_v2()
        #     self._config['version'] = '2.0.0'
        #     self._config['version_updated'] = datetime.datetime.now().isoformat()

    def save(
        self, config_path: Optional[Path] = None, create_backup: bool = True
    ) -> bool:
        """
        Save the current configuration to file.

        Args:
            config_path: Path to save to, defaults to the loaded config path
            create_backup: Whether to create a backup of the current config before saving

        Returns:
            True if save was successful, False otherwise
        """
        save_path = config_path or self._config_path

        try:
            # Create backup of current config if requested
            if create_backup and save_path.exists():
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = save_path.with_suffix(
                    f".backup_{timestamp}{save_path.suffix}"
                )
                import shutil

                shutil.copy2(save_path, backup_path)
                self.logger.info(f"Backup created at: {backup_path}")

            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Add last updated timestamp
            self._config["last_updated"] = datetime.datetime.now().isoformat()

            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)

            self._original_config = deepcopy(self._config)
            self.logger.info(f"Configuration saved to: {save_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        First checks environment variables, then falls back to config file.

        Args:
            key: Configuration key (e.g., "llm.active_provider")
            default: Default value if key doesn't exist

        Returns:
            The configuration value or default
        """
        # First, try to get from environment variable
        # Convert dot notation to a valid environment variable name
        env_var_name = key.upper().replace(".", "_")
        env_value = os.getenv(env_var_name)

        if env_value is not None:
            # Try to convert to appropriate type based on the default
            if isinstance(default, bool):
                return env_value.lower() in ["true", "1", "yes", "on"]
            elif isinstance(default, int):
                try:
                    return int(env_value)
                except ValueError:
                    return default
            elif isinstance(default, float):
                try:
                    return float(env_value)
                except ValueError:
                    return default
            else:
                return env_value

        # If not in environment, fall back to config file
        keys = key.split(".")
        current = self._config

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default

        return current

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "llm.active_provider")
            value: Value to set
        """
        keys = key.split(".")
        current = self._config

        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value
        self.logger.debug(f"Set configuration '{key}' to '{value}'")

    def update_model_config(
        self,
        port: int,
        model_name: str,
        model_path: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        """
        Update model-specific configuration for on-demand model management.

        Args:
            port: Port on which the model server is running
            model_name: Name of the model
            model_path: Path to the model file (optional)
            api_base: API base URL for the model (optional)
        """
        # Cleanse model name to ensure proper format
        if model_name and not model_name.endswith(".gguf"):
            model_name = model_name.replace(
                ".gguf", ""
            )  # Remove duplicate extension if present

        # Update LLM provider configuration
        llama_cpp_config = (
            self._config.setdefault("llm", {})
            .setdefault("providers", {})
            .setdefault("llama_cpp", {})
        )

        if model_path:
            llama_cpp_config["model_path"] = model_path
        llama_cpp_config["model"] = model_name
        if api_base:
            llama_cpp_config["api_base"] = api_base
        else:
            llama_cpp_config["api_base"] = f"http://localhost:{port}/v1"

        # Update active provider
        self._config["llm"]["active_provider"] = "llama_cpp"

        self.logger.info(f"Updated model configuration: {model_name} on port {port}")

    def validate(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required sections
            required_sections = ["llm"]
            for section in required_sections:
                if section not in self._config:
                    raise ConfigValidationError(
                        f"Missing required configuration section: {section}"
                    )

            # Validate LLM configuration
            llm_config = self._config["llm"]
            if "active_provider" not in llm_config:
                raise ConfigValidationError(
                    "Missing 'llm.active_provider' in configuration"
                )

            if "providers" not in llm_config:
                raise ConfigValidationError("Missing 'llm.providers' in configuration")

            # Additional validation can be added as needed

            return True
        except ConfigValidationError:
            raise
        except Exception as e:
            raise ConfigValidationError(f"Configuration validation failed: {e}")

    def get_available_models(self, models_dir: Optional[Path] = None) -> list:
        """
        Get list of available models from the models directory.

        Args:
            models_dir: Directory to scan for models, defaults to project models directory

        Returns:
            List of model information with name, size, and quantization level
        """
        if models_dir is None:
            from .project_root import get_models_dir

            models_dir = get_models_dir()

        models = []
        if not models_dir.exists():
            self.logger.warning(f"Models directory does not exist: {models_dir}")
            return models

        for file_path in models_dir.glob("*.gguf"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    size_mb = stat.st_size / (1024 * 1024)

                    # Extract quantization info from filename if present
                    name = file_path.name
                    quantization = "Unknown"
                    if "q4" in name.lower():
                        quantization = "Q4"
                    elif "q5" in name.lower():
                        quantization = "Q5"
                    elif "q8" in name.lower():
                        quantization = "Q8"
                    elif "f16" in name.lower():
                        quantization = "F16"
                    elif "q2" in name.lower():
                        quantization = "Q2"
                    elif "q3" in name.lower():
                        quantization = "Q3"

                    models.append(
                        {
                            "name": name,
                            "path": str(file_path),
                            "size_mb": round(size_mb, 2),
                            "quantization": quantization,
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"Error processing model file {file_path}: {e}")

        # Sort models by name
        models.sort(key=lambda x: x["name"].lower())
        return models

    def get_config(self) -> Dict[str, Any]:
        """
        Get a copy of the current configuration.

        Returns:
            A copy of the current configuration dictionary
        """
        return deepcopy(self._config)

    def rollback(self) -> bool:
        """
        Rollback configuration to the last saved state.

        Returns:
            True if rollback was successful, False otherwise
        """
        try:
            self._config = deepcopy(self._original_config)
            self.logger.info("Configuration rolled back to last saved state")
            return True
        except Exception as e:
            self.logger.error(f"Failed to rollback configuration: {e}")
            return False

    def get_model_server_config(self) -> Dict[str, Any]:
        """
        Get the current model server configuration.

        Returns:
            Dictionary containing model server configuration
        """
        llm_config = self._config.get("llm", {})
        active_provider = llm_config.get("active_provider", "ollama")
        provider_config = llm_config.get("providers", {}).get(active_provider, {})

        return {
            "active_provider": active_provider,
            "model": provider_config.get("model", ""),
            "api_base": provider_config.get("api_base", "http://localhost:11434/v1"),
            "model_path": provider_config.get("model_path", ""),
        }

    def dry_run_update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a dry-run update to preview changes without saving.

        Args:
            updates: Dictionary of updates to apply

        Returns:
            Dictionary showing what the config would look like after the updates
        """
        temp_config = deepcopy(self._config)

        def _update_recursive(config, updates_dict):
            for key, value in updates_dict.items():
                if (
                    isinstance(value, dict)
                    and key in config
                    and isinstance(config[key], dict)
                ):
                    _update_recursive(config[key], value)
                else:
                    config[key] = value

        _update_recursive(temp_config, updates)
        return temp_config

    def get_config_status(self) -> Dict[str, Any]:
        """
        Get the overall status of the configuration.

        Returns:
            Dictionary containing configuration status information
        """
        return {
            "version": self._config.get("version", "unknown"),
            "last_updated": self._config.get("last_updated", "never"),
            "config_path": str(self._config_path),
            "active_provider": self._config.get("llm", {}).get(
                "active_provider", "none"
            ),
            "model_count": len(self.get_available_models()),
            "valid": self.validate_config_if_loaded(),
        }

    def validate_config_if_loaded(self) -> bool:
        """
        Validate the currently loaded configuration without raising exceptions.

        Returns:
            True if config is valid, False otherwise
        """
        try:
            return self.validate()
        except ConfigValidationError:
            return False
        except Exception:
            return False
