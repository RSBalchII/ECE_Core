"""
Model Loader Module for ECE

This module handles the loading of persona information from POML/JSON files
and manages the correct context loading sequence:
1. POML/JSON Persona (first)
2. Redis Context
3. Current Prompt
4. Tool Outputs
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from xml.etree import ElementTree as ET


class PersonaLoader:
    """
    Loads persona information from POML/JSON files to establish foundational identity,
    protocols, values, and operational context before any processing begins.

    """

    def __init__(self, persona_file_path: str = None):
        """
        Initialize the persona loader.

        Args:
            persona_file_path: Path to the POML/JSON persona file (default: orchestrator.json)
        """
        if persona_file_path is None:
            persona_file_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "poml", "orchestrator.json"
            )

        self.persona_file_path = Path(persona_file_path)
        self.persona_data = None
        self.persona_text = ""

    def load_persona(self) -> str:
        """
        Load the persona information from the POML/JSON file.

        Returns:
            str: Formatted persona information as text
        """
        if not self.persona_file_path.exists():
            raise FileNotFoundError(f"Persona file not found: {self.persona_file_path}")

        try:
            # Try to load as JSON first
            with open(self.persona_file_path, "r", encoding="utf-8") as f:
                self.persona_data = json.load(f)

            # Convert JSON structure to text format for LLM context
            self.persona_text = self._format_persona_as_text()
            return self.persona_text

        except json.JSONDecodeError:
            # If JSON fails, try to load as POML (XML)
            try:
                with open(self.persona_file_path, "r", encoding="utf-8") as f:
                    poml_content = f.read()

                # Parse POML content
                root = ET.fromstring(poml_content)
                self.persona_text = self._parse_poml_to_text(root)
                return self.persona_text
            except ET.ParseError:
                raise ValueError(
                    f"Could not parse {self.persona_file_path} as either JSON or POML"
                )

    def _format_persona_as_text(self) -> str:
        """
        Format persona data from JSON into text suitable for LLM context.

        Returns:
            str: Formatted persona information
        """
        if not self.persona_data:
            return ""

        formatted_parts = []

        # Add identity information
        if "identity" in self.persona_data:
            identity = self.persona_data["identity"]
            if "name" in identity:
                formatted_parts.append(f"Identity: {identity['name']}")
            if "version" in identity:
                formatted_parts.append(f"Version: {identity['version']}")
            if "type" in identity:
                formatted_parts.append(f"Type: {identity['type']}")
            if "core_metaphor" in identity:
                formatted_parts.append(f"Core Metaphor: {identity['core_metaphor']}")

        # Add operational context
        if "operational_context" in self.persona_data:
            op_context = self.persona_data["operational_context"]
            if "current_reality" in op_context:
                formatted_parts.append(
                    f"Current Reality: {op_context['current_reality']}"
                )
            if "primary_node" in op_context:
                formatted_parts.append(f"Primary Node: {op_context['primary_node']}")
            if "directive_heuristic" in op_context:
                formatted_parts.append(
                    f"Directive Heuristic: {op_context['directive_heuristic']}"
                )

        # Add directive information
        if "directive" in self.persona_data:
            directive = self.persona_data["directive"]
            goals = directive.get("goals", [])
            if goals:
                formatted_parts.append("Directive Goals:")
                for i, goal in enumerate(goals, 1):
                    formatted_parts.append(f"  {i}. {goal}")

        # Add protocols
        if "protocols" in self.persona_data:
            protocols = self.persona_data["protocols"]
            if protocols:
                formatted_parts.append("Protocols:")
                for protocol in protocols:
                    if "name" in protocol:
                        formatted_parts.append(
                            f"  - {protocol['name']}: {protocol.get('description', 'No description')}"
                        )

        # Add values
        if "values" in self.persona_data:
            values_list = self.persona_data["values"]
            if values_list:
                formatted_parts.append("Values:")
                for value in values_list:
                    formatted_parts.append(f"  - {value}")

        # Add forbidden behaviors
        if "forbidden" in self.persona_data:
            forbidden_list = self.persona_data["forbidden"]
            if forbidden_list:
                formatted_parts.append("Forbidden Behaviors:")
                for forbidden in forbidden_list:
                    formatted_parts.append(f"  - {forbidden}")

        return "\n\n".join(formatted_parts)

    def _parse_poml_to_text(self, root: ET.Element) -> str:
        """
        Parse POML XML structure to text format.

        Args:
            root: Root element of the parsed POML

        Returns:
            str: Formatted persona information
        """
        formatted_parts = []

        # Parse identity
        identity_elem = root.find("identity")
        if identity_elem is not None:
            formatted_parts.append("Identity Information:")
            for child in identity_elem:
                formatted_parts.append(f"  {child.tag}: {child.text or ''}")

        # Parse operational context
        op_context_elem = root.find("operational_context")
        if op_context_elem is not None:
            formatted_parts.append("Operational Context:")
            for child in op_context_elem:
                formatted_parts.append(f"  {child.tag}: {child.text or ''}")

        # Parse directives
        directive_elem = root.find("directive")
        if directive_elem is not None:
            formatted_parts.append("Directives:")
            for child in directive_elem:
                if child.get("priority"):
                    formatted_parts.append(
                        f"  Priority {child.get('priority')}: {child.text or ''}"
                    )
                else:
                    formatted_parts.append(f"  {child.tag}: {child.text or ''}")

        # Parse protocols
        protocols_elem = root.find("protocols")
        if protocols_elem is not None:
            formatted_parts.append("Protocols:")
            for protocol in protocols_elem.findall("protocol"):
                name = protocol.get("name", "Unnamed Protocol")
                purpose = protocol.find("purpose")
                rules = protocol.findall("rule")

                formatted_parts.append(f"  - {name}")
                if purpose is not None and purpose.text:
                    formatted_parts.append(f"    Purpose: {purpose.text}")
                for rule in rules:
                    formatted_parts.append(f"    Rule: {rule.text}")

        # Parse values
        values_elem = root.find("values")
        if values_elem is not None:
            formatted_parts.append("Values:")
            for value in values_elem:
                formatted_parts.append(f"  - {value.text}")

        # Parse forbidden
        forbidden_elem = root.find("forbidden")
        if forbidden_elem is not None:
            formatted_parts.append("Forbidden:")
            for forbidden in forbidden_elem:
                formatted_parts.append(f"  - {forbidden.text}")

        return "\n\n".join(formatted_parts)


class ContextSequenceManager:
    """
    Manages the complete context loading sequence:
    1. POML/JSON Persona (first)
    2. Redis Context
    3. Current Prompt
    4. Tool Outputs
    """

    def __init__(
        self,
        redis_client=None,
        cache_manager=None,
        persona_loader: PersonaLoader = None,
    ):
        """
        Initialize the context sequence manager.

        Args:
            redis_client: Redis client instance for context retrieval
            cache_manager: CacheManager instance (alternative to redis_client)
            persona_loader: PersonaLoader instance (creates default if None)
        """
        self.redis_client = redis_client
        if cache_manager is not None:
            self.redis_client = cache_manager.redis_client
        self.persona_loader = persona_loader or PersonaLoader()
        self.persona_context = ""

    def load_complete_context(
        self,
        prompt: str,
        tool_outputs: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Load the complete context following the correct sequence.

        Args:
            prompt: The current user prompt
            tool_outputs: Optional dictionary of tool outputs
            session_id: Optional session ID to retrieve specific Redis context

        Returns:
            str: Complete context string following the sequence
        """
        context_parts = []

        # 1. Load persona first
        if not self.persona_context:
            self.persona_context = self.persona_loader.load_persona()
        context_parts.append(f"PERSONA FOUNDATION:\n{self.persona_context}")

        # 2. Load Redis context
        redis_context = self._load_redis_context(session_id)
        if redis_context:
            context_parts.append(f"CONVERSATION HISTORY:\n{redis_context}")

        # 3. Add current prompt
        context_parts.append(f"CURRENT PROMPT:\n{prompt}")

        # 4. Add tool outputs
        if tool_outputs:
            tool_context = self._format_tool_outputs(tool_outputs)
            context_parts.append(f"TOOL OUTPUTS:\n{tool_context}")

        return "\n\n" + "=" * 50 + "\n\n".join(context_parts) + "\n\n" + "=" * 50 + "\n"

    def _load_redis_context(self, session_id: Optional[str] = None) -> str:
        """
        Load context from Redis cache.

        Args:
            session_id: Optional session ID to retrieve specific context

        Returns:
            str: Context from Redis or empty string if not available
        """
        if not self.redis_client:
            return "No Redis client available"

        try:
            # In ECE system, context is stored through the Archivist agent and CacheManager
            # For now, we'll look for cached items related to the session
            context_parts = []

            if session_id:
                # Try to get cached entries related to the current session
                try:
                    # Try to get cached entries with the session ID in the key
                    pattern = f"*{session_id}*"
                    keys = self.redis_client.keys(
                        pattern.encode() if isinstance(pattern, str) else pattern
                    )

                    if keys:
                        for key in sorted(keys):
                            try:
                                key_str = (
                                    key.decode("utf-8")
                                    if isinstance(key, bytes)
                                    else str(key)
                                )
                                # Try to get as simple value first
                                value = self.redis_client.get(key)
                                if value:
                                    if isinstance(value, bytes):
                                        value = value.decode("utf-8")
                                    context_parts.append(
                                        f"[Session Data - {key_str}]: {value}"
                                    )
                                else:
                                    # If not a simple value, try hash format
                                    entry_data = self.redis_client.hgetall(key)
                                    if entry_data:
                                        for field, field_value in entry_data.items():
                                            field_name = (
                                                field.decode("utf-8")
                                                if isinstance(field, bytes)
                                                else str(field)
                                            )
                                            field_val = (
                                                field_value.decode("utf-8")
                                                if isinstance(field_value, bytes)
                                                else str(field_value)
                                            )
                                            if (
                                                field_name == "value"
                                            ):  # Main content field
                                                context_parts.append(field_val)
                                            # else:
                                            #     context_parts.append(f"{field_name}: {field_val}")
                            except Exception as e:
                                continue  # Skip keys that cause errors
                except Exception as e:
                    pass  # Fallback if session-specific approach fails

            # If no session-specific context was found, get more general context
            if not context_parts:
                try:
                    # Try getting general context cache entries
                    recent_keys = self.redis_client.keys("context_cache:*")
                    if recent_keys:
                        for key in sorted(recent_keys, reverse=True)[
                            :5
                        ]:  # Get last 5 entries
                            try:
                                entry_data = self.redis_client.hgetall(key)
                                if entry_data and b"value" in entry_data:
                                    value = entry_data[b"value"].decode("utf-8")
                                    # Only add non-empty values that seem to be actual content
                                    if (
                                        value.strip() and len(value) > 10
                                    ):  # Filter out short/empty entries
                                        context_parts.append(value)
                            except Exception as e:
                                continue
                except:
                    pass

            # If still no context found, try for any conversation-related keys
            if not context_parts:
                try:
                    conversation_keys = self.redis_client.keys("*conversation*")
                    if conversation_keys:
                        for key in conversation_keys[:3]:  # Limit to 3 keys
                            try:
                                value = self.redis_client.get(key)
                                if value:
                                    if isinstance(value, bytes):
                                        value = value.decode("utf-8")
                                    context_parts.append(
                                        f"[Conversation - {key.decode('utf-8')}]: {value}"
                                    )
                            except:
                                continue
                except:
                    pass

            if context_parts:
                return "\n".join(context_parts)
            else:
                return "No previous conversation history found"
        except Exception as e:
            return f"Error retrieving context from Redis: {str(e)}"

    def _format_tool_outputs(self, tool_outputs) -> str:
        """
        Format tool outputs into a readable string.

        Args:
            tool_outputs: Dictionary or list of tool outputs

        Returns:
            str: Formatted tool outputs
        """
        formatted_outputs = []

        if isinstance(tool_outputs, dict):
            # Handle dictionary format as before
            for tool_name, output in tool_outputs.items():
                formatted_outputs.append(f"Tool: {tool_name}")
                if isinstance(output, dict):
                    for key, value in output.items():
                        formatted_outputs.append(f"  {key}: {value}")
                elif isinstance(output, list):
                    # Handle case where output is a list
                    for item in output:
                        formatted_outputs.append(f"  - {item}")
                else:
                    formatted_outputs.append(f"  Output: {output}")
                formatted_outputs.append("")  # Empty line for separation
        elif isinstance(tool_outputs, list):
            # Handle list format
            for i, output in enumerate(tool_outputs):
                if isinstance(output, dict):
                    # If list item is a dict, handle it appropriately
                    formatted_outputs.append(f"Tool Result {i + 1}:")
                    for key, value in output.items():
                        formatted_outputs.append(f"  {key}: {value}")
                else:
                    formatted_outputs.append(f"Tool Result {i + 1}: {output}")
                formatted_outputs.append("")  # Empty line for separation
        else:
            # If it's neither a dict nor a list, just convert to string
            formatted_outputs.append(f"Tool Output: {str(tool_outputs)}")

        return "\n".join(formatted_outputs)


from fastapi import HTTPException
import os
import sys
from pathlib import Path
import subprocess
import time
import psutil
import aiohttp
import asyncio
import logging


# Global singleton instance of ModelManager
_global_model_manager = None


class ModelManager:
    """
    Manages the lifecycle of model servers for on-demand execution:
    - Starts models when needed
    - Stops models when no longer needed
    - Handles model switching
    - Singleton implementation to ensure only one instance across the entire system
    """

    # Class-level variables to share state between instances
    _running_model_process = None
    _current_model = None
    _model_server_port = 8080
    _api_base = "http://localhost:8080/v1"

    def __new__(cls, api_base: str = "http://localhost:8080/v1"):
        """Create a singleton instance of ModelManager."""
        global _global_model_manager
        if _global_model_manager is None:
            _global_model_manager = super(ModelManager, cls).__new__(cls)
            _global_model_manager.__initialized = False
        return _global_model_manager

    def __init__(self, api_base: str = "http://localhost:8080/v1"):
        """Initialize the singleton ModelManager instance."""
        # Prevent re-initialization of singleton
        if getattr(self, "__initialized", False):
            return

        # Make sure logging is properly set up first
        try:
            from ece.common.logging_config import get_logger

            self.logger = get_logger("model_inference")
        except ImportError:
            # Fallback to basic logging if the module isn't available
            import logging

            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.logger.warning(
                "Could not import ECE logging system, using default logging"
            )

        # Set the API base to the provided value if it's different from current
        if ModelManager._api_base != api_base:
            ModelManager._api_base = api_base
            self.logger.info(f"API base updated to: {api_base}")

        # Load default model from config if no model is currently set
        if ModelManager._current_model is None:
            self._load_default_model_from_config()

        self.__initialized = True

    def _load_default_model_from_config(self):
        """Load the default model from config.yaml if available."""
        try:
            import yaml

            config_file = "config.yaml"

            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    config = yaml.safe_load(f)

                llm_config = config.get("llm", {})
                active_provider = llm_config.get("active_provider", "llama_cpp")
                providers = llm_config.get("providers", {})

                if active_provider in providers:
                    provider_config = providers[active_provider]

                    # Get model path from config - try multiple possible keys
                    model_path = provider_config.get(
                        "model_path"
                    ) or provider_config.get("model")

                    if model_path:
                        # Normalize the model path to resolve any issues with duplicate paths or extensions
                        model_path = str(
                            Path(model_path).as_posix()
                        )  # Normalize path separators
                        # Remove any duplicate path segments like '../../models/..\\..\\models\\'
                        if "../" in model_path or "..\\" in model_path:
                            # If the path has malformed segments, try to extract just the filename
                            original_path = Path(model_path)
                            model_filename = original_path.name

                            # Check if it ends with a double extension and fix it
                            if model_filename.endswith(".gguf.gguf"):
                                corrected_filename = model_filename.replace(
                                    ".gguf.gguf", ".gguf"
                                )
                                model_path = str(
                                    original_path.parent / corrected_filename
                                )
                                self.logger.info(
                                    f"Corrected double .gguf extension: {model_path}"
                                )

                        # Extract model name from the normalized path
                        model_name = Path(model_path).stem
                        if model_name and model_name != "":
                            # Set the model properties but do not start the model yet
                            # The model will be started on demand when needed
                            model_file_path = Path("models") / f"{model_name}.gguf"

                            # First check if the configured model file exists directly
                            if model_file_path.exists():
                                ModelManager._current_model = str(model_file_path)
                                self.logger.info(
                                    f"Default model configured from config: {model_name}"
                                )

                                # Update API base if specified in config
                                config_api_base = provider_config.get("api_base")
                                if config_api_base:
                                    ModelManager._api_base = config_api_base
                                    self.logger.info(
                                        f"API base updated from config: {config_api_base}"
                                    )

                                # Extract port from API base if available
                                if config_api_base:
                                    try:
                                        import urllib.parse

                                        parsed = urllib.parse.urlparse(config_api_base)
                                        if parsed.port:
                                            ModelManager._model_server_port = (
                                                parsed.port
                                            )
                                    except Exception as e:
                                        self.logger.warning(
                                            f"Could not parse port from API base: {e}"
                                        )
                            else:
                                # If the model file doesn't exist in the models directory, check if it's an absolute path
                                config_model_path = Path(model_path)
                                if config_model_path.exists():
                                    ModelManager._current_model = str(config_model_path)
                                    self.logger.info(
                                        f"Default model configured from absolute path: {model_path}"
                                    )

                                    # Update API base if specified in config
                                    config_api_base = provider_config.get("api_base")
                                    if config_api_base:
                                        ModelManager._api_base = config_api_base
                                        self.logger.info(
                                            f"API base updated from config: {config_api_base}"
                                        )

                                    # Extract port from API base if available
                                    if config_api_base:
                                        try:
                                            import urllib.parse

                                            parsed = urllib.parse.urlparse(
                                                config_api_base
                                            )
                                            if parsed.port:
                                                ModelManager._model_server_port = (
                                                    parsed.port
                                                )
                                        except Exception as e:
                                            self.logger.warning(
                                                f"Could not parse port from API base: {e}"
                                            )
                                else:
                                    self.logger.warning(
                                        f"Configured model file does not exist: {model_file_path}"
                                    )
                                    # Try to find a fallback model from available models
                                    self._find_fallback_model(model_name)
                        else:
                            self.logger.warning(
                                "Model name could not be extracted from model_path in config"
                            )
                    else:
                        self.logger.warning(
                            f"No model path specified in config for provider: {active_provider}"
                        )
                        # Try to find any available model as fallback
                        self._find_fallback_model()
                else:
                    self.logger.warning(
                        f"Active provider '{active_provider}' not found in config providers"
                    )
                    # Try to find any available model as fallback
                    self._find_fallback_model()
            else:
                self.logger.warning("config.yaml not found, using defaults")
        except Exception as e:
            self.logger.error(f"Error loading default model from config: {e}")

    def _find_fallback_model(self, preferred_model=None):
        """Find a fallback model from available models."""
        available_models = self.get_available_models()

        if available_models:
            # If a preferred model was specified, try to find it first
            if preferred_model:
                for model_info in available_models:
                    if preferred_model in model_info["name"]:
                        model_file_path = Path(model_info["path"])
                        ModelManager._current_model = str(model_file_path)
                        self.logger.info(
                            f"Fallback model selected: {model_info['name']}"
                        )
                        # Update the API base to default localhost:8080 if not already set
                        if ModelManager._api_base == "http://localhost:8080/v1":
                            # Try to assign a port based on model name hash to avoid conflicts
                            model_hash = (
                                abs(hash(model_info["name"])) % 15
                            )  # 0-14 range
                            port = 8080 + model_hash
                            ModelManager._model_server_port = port
                            ModelManager._api_base = f"http://localhost:{port}/v1"
                        return True

            # If preferred model not found or wasn't specified, use the first available model
            model_info = available_models[0]
            model_file_path = Path(model_info["path"])
            ModelManager._current_model = str(model_file_path)
            self.logger.info(f"Fallback model selected: {model_info['name']}")
            # Update the API base to default localhost:8080 if not already set
            if ModelManager._api_base == "http://localhost:8080/v1":
                # Try to assign a port based on model name hash to avoid conflicts
                model_hash = abs(hash(model_info["name"])) % 15  # 0-14 range
                port = 8080 + model_hash
                ModelManager._model_server_port = port
                ModelManager._api_base = f"http://localhost:{port}/v1"
            return True
        else:
            self.logger.error("No models available for fallback")
            return False

    @property
    def running_model_process(self):
        return ModelManager._running_model_process

    @running_model_process.setter
    def running_model_process(self, value):
        ModelManager._running_model_process = value

    @property
    def current_model(self):
        return ModelManager._current_model

    @current_model.setter
    def current_model(self, value):
        ModelManager._current_model = value

    @property
    def model_server_port(self):
        return ModelManager._model_server_port

    @model_server_port.setter
    def model_server_port(self, value):
        ModelManager._model_server_port = value

    @property
    def api_base(self):
        return ModelManager._api_base

    @api_base.setter
    def api_base(self, value):
        ModelManager._api_base = value

    def get_available_models(self) -> list:
        """
        Scan the models directory to find available GGUF model files.

        Returns:
            list: Available model information with name, size, quantization, etc.
        """
        models_dir = Path("models")
        if not models_dir.exists():
            return []

        available_models = []
        for model_file in models_dir.glob("*.gguf"):
            # Extract model information from filename
            model_name = model_file.stem
            file_size = model_file.stat().st_size  # Size in bytes

            # Try to determine quantization from filename
            quantization = "unknown"
            name_lower = model_name.lower()
            if "q4" in name_lower:
                quantization = "Q4"
            elif "q5" in name_lower:
                quantization = "Q5"
            elif "q6" in name_lower:
                quantization = "Q6"
            elif "q8" in name_lower:
                quantization = "Q8"
            elif "f16" in name_lower:
                quantization = "F16"
            elif "q2" in name_lower:
                quantization = "Q2"
            elif "q3" in name_lower:
                quantization = "Q3"

            # Determine architecture from filename
            architecture = "unknown"
            if "llama" in name_lower:
                architecture = "LLaMA"
            elif "mistral" in name_lower:
                architecture = "Mistral"
            elif "jamba" in name_lower:
                architecture = "Jamba"
            elif "gemma" in name_lower:
                architecture = "Gemma"
            elif "qwen" in name_lower:
                architecture = "Qwen"
            elif "deepseek" in name_lower:
                architecture = "DeepSeek"
            elif "moe" in name_lower:
                architecture = "MoE"

            # Convert size to human readable format
            size_str = self._bytes_to_readable(file_size)

            available_models.append(
                {
                    "name": model_name,
                    "path": str(model_file),
                    "size": size_str,
                    "quantization": quantization,
                    "architecture": architecture,
                    "parameters": self._guess_parameters(model_name),
                }
            )

        return available_models

    def _bytes_to_readable(self, bytes_size: int) -> str:
        """Convert bytes to human readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} TB"

    def _guess_parameters(self, model_name: str) -> str:
        """Guess the number of parameters based on the model name."""
        name_lower = model_name.lower()

        if "1b" in name_lower or "1_0b" in name_lower:
            return "1B"
        elif "3b" in name_lower or "3_0b" in name_lower:
            return "3B"
        elif "7b" in name_lower or "7_0b" in name_lower:
            return "7B"
        elif "13b" in name_lower:
            return "13B"
        elif "14b" in name_lower:
            return "14B"
        elif "30b" in name_lower:
            return "30B"
        elif "34b" in name_lower:
            return "34B"
        elif "70b" in name_lower:
            return "70B"
        elif "72b" in name_lower:
            return "72B"
        else:
            # Try to extract a number followed by 'b'
            import re

            matches = re.findall(r"(\d+)b", name_lower)
            if matches:
                return f"{matches[0]}B"
            return "unknown"

    def get_current_model(self) -> str:
        """
        Get the name/path of the currently running model.

        Returns:
            str: Current model name or None if no model is running
        """
        return (
            self.current_model if self.current_model else "No model currently running"
        )

    async def ensure_model_running(self) -> bool:
        """
        Ensure the model server is running, start it if necessary.

        Returns:
            bool: True if model is running or started successfully, False otherwise
        """
        if await self.check_model_health():
            self.logger.info("Model server is already running and healthy.")
            return True
        else:
            self.logger.info("Model server is not running. Attempting to start...")
            # Try to start the model server
            return await self.start_model_server()

    async def check_model_health(self) -> bool:
        """
        Check if the model server is responding to requests.

        Returns:
            bool: True if model server is healthy, False otherwise
        """
        try:
            # Make a simple request to check model health
            health_url = (
                self.api_base.replace("/v1", "/health")
                if "/v1" in self.api_base
                else f"{self.api_base}/health"
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    health_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    def _wait_for_model_server(self, port: int, timeout: int = 30) -> bool:
        """
        Wait for the model server to become available at the specified port.

        Args:
            port (int): Port number where the model server should be running
            timeout (int): Maximum time to wait in seconds

        Returns:
            bool: True if server becomes available within timeout, False otherwise
        """
        import time
        import socket

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Check if we can connect to the port
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)  # 1 second timeout for connection check
                result = sock.connect_ex(("localhost", port))
                sock.close()

                if result == 0:
                    # Port is open, now check if it responds to health endpoint
                    # Use a simple HTTP request to check if the server is truly ready
                    health_url = f"http://localhost:{port}/health"
                    try:
                        import requests

                        response = requests.get(health_url, timeout=5)

                        if response.status_code == 200:
                            self.logger.info(
                                f"Model server is available at localhost:{port}"
                            )
                            return True
                        else:
                            # Server is responding but not with 200, might still be initializing
                            self.logger.debug(
                                f"Model server responded with status {response.status_code} at localhost:{port}"
                            )
                    except (requests.RequestException, ImportError):
                        # requests not available or timed out, fall back to just port check
                        self.logger.info(
                            f"Model server port is open at localhost:{port}"
                        )
                        return True
                else:
                    self.logger.debug(f"Model server port {port} not yet available")
            except Exception as e:
                self.logger.debug(f"Error checking model server availability: {e}")

            time.sleep(1)  # Wait 1 second before checking again

        self.logger.warning(f"Timeout waiting for model server to start on port {port}")
        return False

    async def start_model_server(self) -> bool:
        """
        Start the model server by actually launching the llama.cpp server process.
        """
        try:
            # If we already have a running process, check if it's still alive
            if self.running_model_process and self.running_model_process.poll() is None:
                # Process is still running, check health
                if await self.check_model_health():
                    self.logger.info("Model server is already running and healthy.")
                    return True
                else:
                    # Process is running but not responding, restart it
                    self.logger.info(
                        "Model server process is running but not responding. Restarting..."
                    )
                    self.stop_model()

            # If we don't have a current model but have a model name, try to start it
            if not self.current_model:
                self.logger.warning(
                    "No current model selected. Attempting to load from configuration..."
                )
                # Attempt to load the default model from config again in case it wasn't loaded during init
                self._load_default_model_from_config()

                if not self.current_model:
                    self.logger.error(
                        "No model configured. Cannot start model server without a model."
                    )
                    return False

            # Parse the current API base to extract the port
            import urllib.parse

            parsed = urllib.parse.urlparse(self.api_base)
            port = (
                parsed.port if parsed.port else 8080
            )  # Default to 8080 if no port is specified

            # Start the actual model server process with the correct port
            model_name = Path(self.current_model).stem if self.current_model else None
            if model_name:
                success = self.start_model(
                    model_name, port=port
                )  # Pass the port from API base

                if success:
                    self.logger.info("Model server started successfully.")
                    # Wait a moment for the server to initialize
                    await asyncio.sleep(2)
                    return True
                else:
                    self.logger.error("Failed to start model server process.")
                    return False
            else:
                self.logger.error("Could not extract model name to start.")
                return False
        except Exception as e:
            self.logger.error(f"Error starting model server: {e}")
            return False

    def select_model(self, model_name: str) -> bool:
        """
        Select a model by name and start it if not already running.

        Args:
            model_name: Name of the model to select

        Returns:
            bool: True if model selected and started successfully, False otherwise
        """
        try:
            # Check if the requested model is already running
            if self.current_model and model_name in self.current_model:
                self.logger.info(f"Model {model_name} is already running.")
                return True

            # Stop any currently running model
            if self.running_model_process:
                self.stop_model()

            # Start the requested model
            # Parse the current API base to extract the port
            import urllib.parse

            parsed = urllib.parse.urlparse(self.api_base)
            port = (
                parsed.port if parsed.port else 8080
            )  # Default to 8080 if no port is specified

            success = self.start_model(model_name, port=port)

            if success:
                self.logger.info(
                    f"Model {model_name} selected and started successfully."
                )
                return True
            else:
                self.logger.error(f"Failed to start model: {model_name}")
                return False
        except Exception as e:
            self.logger.error(f"Error selecting model {model_name}: {e}")
            return False

    def start_model(self, model_name: str, port: int = None) -> bool:
        """
        Start a specific model server on demand.

        Args:
            model_name: Name of the model to start
            port: Port number to run the model on (will be assigned if not provided)

        Returns:
            bool: True if model started successfully, False otherwise
        """
        if port is None:
            port = self._find_available_port()

        models_dir = Path("models")
        model_path = models_dir / f"{model_name}.gguf"

        if not model_path.exists():
            # Try without .gguf extension
            model_path = models_dir / model_name
            if not model_path.exists() and not model_name.endswith(".gguf"):
                model_path = models_dir / f"{model_name}"
                if not model_path.exists():
                    raise HTTPException(
                        status_code=404, detail=f"Model file not found: {model_name}"
                    )

        # Check if another model server is already running and stop it
        if self.running_model_process and self.running_model_process.poll() is None:
            self.stop_model()

        # Find the llama.cpp server executable
        # First try the newer llama-server.exe name, then fall back to server.exe
        llama_server_paths = [
            Path("llama.cpp") / "build" / "bin" / "Release" / "llama-server.exe",
            Path("..") / "llama.cpp" / "build" / "bin" / "Release" / "llama-server.exe",
            Path("llama.cpp") / "build" / "bin" / "Release" / "server.exe",
            Path("..") / "llama.cpp" / "build" / "bin" / "Release" / "server.exe",
        ]

        llama_server_path = None
        for path in llama_server_paths:
            if path.exists():
                llama_server_path = path
                break

        # If not found in standard locations, try platform-specific names
        if llama_server_path is None:
            import platform

            if platform.system() == "Linux":
                llama_server_paths = [
                    Path("llama.cpp") / "server" / "llama-server",
                    Path("..") / "llama.cpp" / "server" / "llama-server",
                ]
                for path in llama_server_paths:
                    if path.exists():
                        llama_server_path = path
                        break
            elif platform.system() == "Darwin":  # macOS
                llama_server_paths = [
                    Path("llama.cpp") / "server" / "llama-server",
                    Path("..") / "llama.cpp" / "server" / "llama-server",
                ]
                for path in llama_server_paths:
                    if path.exists():
                        llama_server_path = path
                        break

        if llama_server_path is None:
            raise HTTPException(
                status_code=500, detail="llama.cpp server executable not found"
            )

        try:
            # Start the model server in a subprocess
            cmd = [
                str(llama_server_path),
                "-m",
                str(model_path),
                "-c",
                "4096",
                "--port",
                str(port),
                "--host",
                "127.0.0.1",
                "-t",
                "8",  # threads
                "--n-gpu-layers",
                "-1",  # Use GPU if available
            ]

            # Start the model server subprocess with proper logging configuration
            import threading
            import queue

            # Create the process with stdout and stderr redirected
            self.running_model_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
            )

            # Create a thread to capture stdout
            def capture_output(pipe, level="INFO"):
                for line in iter(pipe.readline, ""):
                    if line.strip():  # Only log non-empty lines
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                        log_entry = (
                            f"{timestamp} [{level}] model_inference:1 - {line.strip()}"
                        )
                        with open(
                            "logs/debug_log_model_inference.txt", "a", encoding="utf-8"
                        ) as f:
                            f.write(log_entry + "\n")
                pipe.close()

            # Start threads to capture both stdout and stderr
            stdout_thread = threading.Thread(
                target=capture_output, args=(self.running_model_process.stdout, "INFO")
            )
            stderr_thread = threading.Thread(
                target=capture_output, args=(self.running_model_process.stderr, "ERROR")
            )

            # Make threads daemon so they don't prevent script exit
            stdout_thread.daemon = True
            stderr_thread.daemon = True

            # Start the threads
            stdout_thread.start()
            stderr_thread.start()

            # Store the model and port information
            self.current_model = str(model_path)
            self.model_server_port = port

            # Update the API base with the new port
            self.api_base = f"http://localhost:{port}/v1"

            # Wait for the server to start with health check
            if not self._wait_for_model_server(port, timeout=30):
                raise HTTPException(
                    status_code=500,
                    detail="Model server failed to start within timeout period",
                )

            # Check if the process is still running
            if self.running_model_process.poll() is not None:
                # Process has already terminated, get the error output
                _, stderr = self.running_model_process.communicate()
                raise HTTPException(
                    status_code=500,
                    detail=f"Model server failed to start: {stderr.decode()}",
                )

            return True
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to start model server: {str(e)}"
            )

    def stop_model(self) -> bool:
        """
        Stop the currently running model server.

        Returns:
            bool: True if model stopped successfully, False otherwise
        """
        if self.running_model_process:
            try:
                # Terminate the process gracefully
                self.running_model_process.terminate()

                # Wait for the process to terminate
                try:
                    self.running_model_process.wait(timeout=10)  # Wait up to 10 seconds
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    self.running_model_process.kill()
                    self.running_model_process.wait()  # Wait for force kill to complete

                self.running_model_process = None
                self.current_model = None
                self.api_base = "http://localhost:8080/v1"  # Reset to default
                return True
            except Exception as e:
                print(f"Error stopping model: {e}")
                return False
        return True  # If no process was running, consider it stopped

    def restart_model(self, model_name: str) -> bool:
        """
        Restart the model server with a potentially different model.

        Args:
            model_name: Name of the model to restart with

        Returns:
            bool: True if restart was successful
        """
        self.stop_model()
        return self.start_model(model_name)

    def refresh_configuration(self):
        """
        Refresh the configuration by reloading from config.yaml and clearing any cached values.
        """
        # Reset current model and related information
        ModelManager._current_model = None
        ModelManager._api_base = "http://localhost:8080/v1"  # Reset to default
        ModelManager._model_server_port = 8080  # Reset to default

        # Reload default model from config
        self._load_default_model_from_config()

        self.logger.info("ModelManager configuration refreshed from config.yaml")

    def get_model_status(self) -> dict:
        """
        Get the status of the model management system.

        Returns:
            dict: Status information about running models
        """
        is_running = False
        if self.running_model_process:
            # Check if the process is still alive
            is_running = self.running_model_process.poll() is None

        return {
            "is_model_running": is_running,
            "current_model": self.current_model,
            "model_server_port": self.model_server_port,
            "api_base": self.api_base,
            "available_models_count": len(self.get_available_models()),
        }

    def _find_available_port(self) -> int:
        """
        Find an available port starting from 8080 and going up.

        Returns:
            int: Available port number
        """
        start_port = 8080
        for port in range(
            start_port, start_port + 15
        ):  # Check 15 ports starting from 8080
            if self._is_port_available(port):
                return port

        raise HTTPException(
            status_code=500, detail="No available ports found for model server"
        )

    def _is_port_available(self, port: int) -> bool:
        """
        Check if a port is available.

        Args:
            port: Port number to check

        Returns:
            bool: True if port is available, False otherwise
        """
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except socket.error:
                return False


# For testing purposes
if __name__ == "__main__":
    # Example usage
    persona_loader = PersonaLoader()
    context_manager = ContextSequenceManager(persona_loader=persona_loader)

    # Example context loading
    complete_context = context_manager.load_complete_context(
        prompt="How can I implement a new agent in the ECE system?",
        tool_outputs={
            "web_search": {
                "query": "ECE agent implementation",
                "results": ["Result 1", "Result 2"],
            },
            "file_reader": {
                "file": "agent_example.py",
                "content_preview": "Class definition for example agent...",
            },
        },
    )

    print(complete_context)
