"""
Enhanced Orchestrator Agent with prompt management and stability improvements.
"""

import os
import subprocess
import aiohttp
import asyncio
import yaml
import traceback
import logging
from typing import Optional, Dict, Any, List
from xml.etree import ElementTree as ET
from urllib.parse import urlparse
import json
import time

from ece.agents.tier2.conversational_agent import ConversationalAgent
from ece.agents.tier2.explorer_agent import ExplorerAgent
from ece.agents.tier2.critique_agent import CritiqueAgent
from ece.agents.tier2.web_search_agent import WebSearchAgent
from ece.common.sandbox import run_code_in_sandbox
from ece.components.context_cache.cache_manager import CacheManager
from ece.agents.tier1.orchestrator.archivist_client import ArchivistClient
from ece.common.prompt_manager import PromptManager, PromptConfig
from ece.common.logging_config import get_logger
from utcp.utcp_client import UtcpClient
from utcp.data.tool import Tool
from ece.agents.common.trm_client import TRMClient, TRMConfig
from ece.agents.common.markovian_thinker import (
    MarkovianThinker,
    MarkovianConfig,
    ReasoningAnalyzer,
)
from ece.agents.common.model_loader import (
    PersonaLoader,
    ContextSequenceManager,
    ModelManager,
)
# Removed ThinkerCoordinator as it's no longer used since parallel thinking was replaced with tool usage

# Set up logging for the orchestrator
logger = get_logger("orchestrator")


# Removed BaseThinker and SynthesisThinker classes as they were part of the deprecated parallel thinking approach
# The system now uses direct model calls and tool usage instead of parallel thinking with multiple thinkers

# Removed get_all_thinkers function as it was part of the deprecated parallel thinking approach
# The system now uses direct model calls and tool usage instead of parallel thinking with multiple thinkers


class EnhancedOrchestratorAgent:
    """
    Enhanced Orchestrator Agent with improved prompt management and stability features.
    """

    def __init__(self, session_id: str, config_path: str = "config.yaml"):
        try:
            # Use the new configuration system that supports environment variables
            from ece.common.config_loader import get_config

            self.config_loader = get_config()

            # Load configuration using the new system (with environment variable support)
            active_provider = self.config_loader.get_active_provider()
            provider_config = self.config_loader.get_llm_config(active_provider)

            logger.debug(f"Active provider: {active_provider}")
            logger.debug(f"Provider config: {provider_config}")

            self.max_tokens = 32768
            # Check if the active provider is llama_cpp to use higher token limit
            if active_provider == "llama_cpp":
                self.max_tokens = 131072
            self.temperature = (
                provider_config.get("temperature", 0.7) if provider_config else 0.7
            )
            logger.debug(
                f"Max tokens: {self.max_tokens}, Temperature: {self.temperature}"
            )

            prompt_config = PromptConfig(
                max_tokens=self.max_tokens, reserved_tokens=1000, strategy="intelligent"
            )
            self.prompt_manager = PromptManager(prompt_config)
            logger.debug("Initialized prompt manager")

            self.session_id = session_id
            self.llm_semaphore = asyncio.Semaphore(1)
            logger.debug("Initialized session and semaphore")

            # Assign logger to instance variable
            self.logger = logger

            # Use environment variable or config for model and API base
            llm_model = provider_config.get(
                "model", provider_config.get("model_path", "default-model")
            )
            api_base = provider_config.get("api_base", "http://localhost:11434/v1")
            logger.debug(f"LLM model: {llm_model}, API base: {api_base}")

            # Get synthesis model from config or environment
            synthesis_model = self.config_loader.get(
                "ThinkerAgent.synthesis_model", llm_model
            )
            logger.debug(f"Synthesis model: {synthesis_model}")

            # Create a single, shared aiohttp.ClientSession
            timeout = aiohttp.ClientTimeout(total=300)
            self.http_client = aiohttp.ClientSession(timeout=timeout)
            logger.debug("Initialized HTTP client")

            # Note: Parallel thinking infrastructure has been removed in favor of direct model calls and tool usage
            # The thinkers and synthesis_thinker are no longer needed in the main processing flow
            logger.debug(
                "Skipping parallel thinking initialization (deprecated in favor of direct model calls and tools)"
            )

            # Get archivist URL from config or environment
            archivist_url = self.config_loader.get(
                "archivist.url", "http://localhost:8003"
            )
            self.archivist_client = ArchivistClient(base_url=archivist_url)
            logger.debug(f"Initialized archivist client with URL: {archivist_url}")

            self.cache_manager = CacheManager()
            logger.debug("Initialized cache manager")

            # Configure UTCP for decentralized approach - each service serves its own UTCP manual
            # Make these configurable from environment variables if needed
            orchestrator_port = os.getenv("ORCHESTRATOR_PORT", "8000")
            distiller_port = os.getenv("DISTILLER_PORT", "8001")
            qlearning_port = os.getenv("QLEARNING_PORT", "8002")
            archivist_port = os.getenv("ARCHIVIST_PORT", "8003")
            injector_port = os.getenv("INJECTOR_PORT", "8004")
            filesystem_port = os.getenv("FILESYSTEM_PORT", "8006")
            websearch_port = os.getenv("WEBSEARCH_PORT", "8007")

            self.utcp_config = {
                "manual_call_templates": [
                    {
                        "name": "distiller_utcp",
                        "call_template_type": "http",
                        "url": f"http://localhost:{distiller_port}/utcp",
                    },
                    {
                        "name": "qlearning_utcp",
                        "call_template_type": "http",
                        "url": f"http://localhost:{qlearning_port}/utcp",
                    },
                    {
                        "name": "archivist_utcp",
                        "call_template_type": "http",
                        "url": f"http://localhost:{archivist_port}/utcp",
                    },
                    {
                        "name": "injector_utcp",
                        "call_template_type": "http",
                        "url": f"http://localhost:{injector_port}/utcp",
                    },
                    {
                        "name": "filesystem_utcp",
                        "call_template_type": "http",
                        "url": f"http://localhost:{filesystem_port}/utcp",
                    },
                    {
                        "name": "websearch_utcp",
                        "call_template_type": "http",
                        "url": f"http://localhost:{websearch_port}/utcp",
                    },
                ],
                # Additional UTCP configuration options for different communication protocols
                "supported_protocols": [
                    "http",  # Standard HTTP/REST API calls
                    "sse",  # Server-Sent Events for streaming
                    "websocket",  # WebSocket for bidirectional communication
                    "mcp",  # Model Context Protocol
                    "cli",  # Command-line interface tools
                ],
                # Configure protocol fallback options
                "protocol_fallback_order": ["http", "sse", "websocket", "mcp", "cli"],
            }
            self.utcp_client = None
            logger.debug("Initialized UTCP config with decentralized endpoints")

            trm_config = TRMConfig(
                api_base=api_base,  # Use the same API base as the main LLM
                model=llm_model,  # Use the same model as the main LLM
            )
            self.trm_client = TRMClient(trm_config)
            logger.debug("Initialized TRM client")

            markovian_config = MarkovianConfig(
                thinking_context_size=8192,
                markovian_state_size=4096,
                iteration_cap=5,
                temperature=0.6,
                api_base=api_base,
                model=llm_model,
            )
            self.markovian_thinker = MarkovianThinker(markovian_config)
            logger.debug("Initialized Markovian thinker")

            # Initialize model manager for on-demand model starting/stopping
            # Use API base from config which may have been updated by environment variables
            try:
                self.model_manager = ModelManager(api_base)
                logger.debug("Initialized model manager for on-demand model handling")
                logger.debug(f"Model manager configured with API base: {api_base}")
            except Exception as e:
                logger.error(f"Error initializing model manager: {e}")
                # Initialize with default settings as fallback
                self.model_manager = ModelManager()
                logger.info(
                    "Model manager initialized with default settings after error"
                )

            # Initialize persona loader and context sequence manager for correct loading order
            self.persona_loader = PersonaLoader()
            self.context_manager = ContextSequenceManager(
                redis_client=self.cache_manager.redis_client,
                persona_loader=self.persona_loader,
            )
            logger.debug("Initialized persona loader and context sequence manager")

            logger.info("EnhancedOrchestratorAgent initialized successfully")
        except Exception as e:
            import traceback

            error_details = f"Error initializing EnhancedOrchestratorAgent: {str(e)}\nTraceback:\n{traceback.format_exc()}"
            logger.error(error_details)
            raise

    async def process_prompt_with_context_management(self, user_prompt: str) -> str:
        try:
            # Analyze intent to determine if tools are needed
            tool_intent = self._analyze_intent_for_tools(user_prompt)

            if tool_intent["needs_tools"]:
                # Process with tools based on intent
                tool_results = []

                if tool_intent["filesystem"]:
                    self.logger.info("Detected need for filesystem operations")
                    try:
                        fs_result = await self.handle_filesystem_request()
                        tool_results.append({"type": "filesystem", "result": fs_result})
                    except Exception as e:
                        self.logger.error(f"Error in filesystem tool call: {e}")
                        tool_results.append({"type": "filesystem", "error": str(e)})

                if tool_intent["web_search"]:
                    self.logger.info("Detected need for web search operations")
                    try:
                        web_result = await self.handle_web_search_request(user_prompt)
                        tool_results.append(
                            {"type": "web_search", "result": web_result}
                        )
                    except Exception as e:
                        self.logger.error(f"Error in web search tool call: {e}")
                        tool_results.append({"type": "web_search", "error": str(e)})

                # Load complete context following the correct sequence using ContextSequenceManager
                complete_context = await self.context_manager.load_complete_context(
                    prompt=user_prompt,
                    tool_outputs=tool_results,
                    session_id=self.session_id,
                )

                # Get the final response based on complete context
                result = await self.direct_model_response(complete_context)

                # Return only the final response for clean output
                # Debug information is available in logs when needed
                return result

            elif ReasoningAnalyzer.should_use_markovian_thinking(user_prompt):
                self.logger.info("Using Markovian thinking for complex reasoning")
                return await self._process_with_markovian_thinking(user_prompt)
            else:
                self.logger.info("Using direct model response for simpler reasoning")

                # Load complete context following the correct sequence
                complete_context = await self.context_manager.load_complete_context(
                    prompt=user_prompt, tool_outputs=None, session_id=self.session_id
                )

                stats = self.prompt_manager.get_context_usage_stats(complete_context)
                self.logger.info(f"Context usage stats: {json.dumps(stats, indent=2)}")
                if stats["over_limit"]:
                    self.logger.warning(
                        f"Prompt was adjusted due to context overflow: {stats}"
                    )

                # Use a direct model call instead of parallel thinking
                result = await self.direct_model_response(complete_context)
                # Return only the final response for clean output
                # Debug information is available in logs when needed
                return result
        except Exception as e:
            self.logger.error(f"Error in process_prompt_with_context_management: {e}")
            self.logger.error(traceback.format_exc())
            return f"Error processing prompt: {str(e)}"

    async def _process_with_markovian_thinking(self, user_prompt: str) -> str:
        try:
            # Analyze intent to determine if tools are needed even in Markovian thinking
            tool_intent = self._analyze_intent_for_tools(user_prompt)

            if tool_intent["needs_tools"]:
                # Process with tools first, even in Markovian mode
                tool_results = []

                if tool_intent["filesystem"]:
                    self.logger.info(
                        "Detected need for filesystem operations in Markovian thinking"
                    )
                    try:
                        fs_result = await self.handle_filesystem_request()
                        tool_results.append({"type": "filesystem", "result": fs_result})
                    except Exception as e:
                        self.logger.error(
                            f"Error in filesystem tool call during Markovian thinking: {e}"
                        )
                        tool_results.append({"type": "filesystem", "error": str(e)})

                if tool_intent["web_search"]:
                    self.logger.info(
                        "Detected need for web search operations in Markovian thinking"
                    )
                    try:
                        web_result = await self.handle_web_search_request(user_prompt)
                        tool_results.append(
                            {"type": "web_search", "result": web_result}
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error in web search tool call during Markovian thinking: {e}"
                        )
                        tool_results.append({"type": "web_search", "error": str(e)})

                # Load complete context with tools following the correct sequence
                complete_context = await self.context_manager.load_complete_context(
                    prompt=user_prompt,
                    tool_outputs=tool_results,
                    session_id=self.session_id,
                )

                # Perform Markovian reasoning with complete context
                result = await self.markovian_thinker.markovian_reasoning_loop(
                    initial_query=user_prompt, context=complete_context
                )

                self.cache_manager.store(f"{self.session_id}:markovian_result", result)
                self.logger.info(
                    f"Markovian reasoning completed with tools, result length: {len(result)} characters"
                )

                # Return only the final result for clean output
                # Debug information is available in logs when needed
                return result
            else:
                # Standard Markovian thinking without tools but with complete context sequence
                complete_context = await self.context_manager.load_complete_context(
                    prompt=user_prompt, tool_outputs=None, session_id=self.session_id
                )

                result = await self.markovian_thinker.markovian_reasoning_loop(
                    initial_query=user_prompt, context=complete_context
                )
                self.cache_manager.store(f"{self.session_id}:markovian_result", result)
                self.logger.info(
                    f"Markovian reasoning completed, result length: {len(result)} characters"
                )
                return result
        except Exception as e:
            self.logger.error(f"Error in Markovian reasoning: {e}")
            self.logger.error(traceback.format_exc())
            self.logger.info(
                "Falling back to direct model response after Markovian reasoning failure"
            )
            # Also check for tools in the fallback path
            tool_intent = self._analyze_intent_for_tools(user_prompt)

            if tool_intent["needs_tools"]:
                tool_results = []

                if tool_intent["filesystem"]:
                    try:
                        fs_result = await self.handle_filesystem_request()
                        tool_results.append({"type": "filesystem", "result": fs_result})
                    except Exception as e:
                        tool_results.append({"type": "filesystem", "error": str(e)})

                if tool_intent["web_search"]:
                    try:
                        web_result = await self.handle_web_search_request(user_prompt)
                        tool_results.append(
                            {"type": "web_search", "result": web_result}
                        )
                    except Exception as e:
                        tool_results.append({"type": "web_search", "error": str(e)})

                # Load complete context with tools for fallback
                complete_context = await self.context_manager.load_complete_context(
                    prompt=user_prompt,
                    tool_outputs=tool_results,
                    session_id=self.session_id,
                )
            else:
                # Load complete context without tools for fallback
                complete_context = await self.context_manager.load_complete_context(
                    prompt=user_prompt, tool_outputs=None, session_id=self.session_id
                )

            result = await self.direct_model_response(complete_context)
            # Return only the final result for clean output
            # Debug information is available in logs when needed
            return result

    async def handle_filesystem_request(self, path: str = ".") -> str:
        try:
            # Ensure UTCP client is initialized
            success = await self._ensure_utcp_client()
            if not success or self.utcp_client is None:
                return f"UTCP client not available for filesystem operations. Please ensure UTCP is properly configured and dependencies are installed."

            # Search for all available tools
            all_tools = await self.utcp_client.search_tools("", limit=100)
            self.logger.info(f"Found {len(all_tools)} total tools via UTCP")

            # Filter for filesystem tools
            fs_tools = [
                tool
                for tool in all_tools
                if "filesystem" in tool.name.lower()
                or "filesystem" in getattr(tool, "tags", [])
            ]
            self.logger.info(
                f"Available filesystem tools: {[tool.name for tool in fs_tools]}"
            )

            if not fs_tools:
                return "No filesystem tools available via UTCP"

            # Look for specific filesystem operations
            for tool in fs_tools:
                tool_name_lower = tool.name.lower()

                # Look for list_directory tool specifically
                if any(
                    name in tool_name_lower
                    for name in ["list", "dir", "directory", "browse", "scan"]
                ):
                    result = await self.utcp_client.call_tool(tool.name, {"path": path})
                    return f"Directory listing for '{path}': {result}"

                # Look for read_file tool specifically
                elif any(
                    name in tool_name_lower for name in ["read", "file", "content"]
                ):
                    # We need a specific file path for reading, so let's list first to show available files
                    # Find a list tool in all available filesystem tools
                    list_tool = next(
                        (
                            t
                            for t in fs_tools
                            if any(
                                n in t.name.lower()
                                for n in ["list", "dir", "directory"]
                            )
                        ),
                        None,
                    )
                    if list_tool:
                        list_result = await self.utcp_client.call_tool(
                            list_tool.name, {"path": path}
                        )
                        return f"Files in '{path}': {list_result}. For specific file content, please request to read a specific file."

            # If no specific tool found, use the first available filesystem tool
            if fs_tools:
                result = await self.utcp_client.call_tool(
                    fs_tools[0].name, {"path": path}
                )
                return f"Filesystem operation result: {result}"

            return "No suitable filesystem tool found"
        except Exception as e:
            self.logger.error(f"Error in handle_filesystem_request: {e}")
            self.logger.error(traceback.format_exc())
            return f"Error handling filesystem request: {str(e)}"

    async def handle_web_search_request(self, query: str) -> str:
        try:
            # Ensure UTCP client is initialized
            success = await self._ensure_utcp_client()
            if not success or self.utcp_client is None:
                return f"UTCP client not available for web search operations. Please ensure UTCP is properly configured and dependencies are installed."

            # Search for all available tools
            all_tools = await self.utcp_client.search_tools("", limit=100)
            self.logger.info(f"Found {len(all_tools)} total tools via UTCP")

            # Filter for web search tools
            web_tools = [
                tool
                for tool in all_tools
                if "web" in tool.name.lower()
                or "web" in getattr(tool, "tags", [])
                or "search" in tool.name.lower()
                or "tavily" in tool.name.lower()  # Common web search provider
            ]
            self.logger.info(
                f"Available web search tools: {[tool.name for tool in web_tools]}"
            )

            if not web_tools:
                return "No web search tools available via UTCP"

            # Look for search-specific tools
            for tool in web_tools:
                tool_name_lower = tool.name.lower()

                if "search" in tool_name_lower or "tavily" in tool_name_lower:
                    result = await self.utcp_client.call_tool(
                        tool.name, {"query": query}
                    )
                    self.logger.info(f"Web search result received from {tool.name}")
                    return f"Web search results for '{query}': {result}"

            # If no specific search tool found, use the first available web tool
            if web_tools:
                result = await self.utcp_client.call_tool(
                    web_tools[0].name, {"query": query}
                )
                self.logger.info(f"Web tool result received from {web_tools[0].name}")
                return f"Web search results for '{query}': {result}"

            return "No suitable web search tool found"
        except Exception as e:
            self.logger.error(f"Error in handle_web_search_request: {e}")
            self.logger.error(traceback.format_exc())
            return f"Error handling web search request: {str(e)}"

    def _analyze_intent_for_tools(self, user_prompt: str) -> Dict[str, bool]:
        """
        Analyze the user prompt to determine if tools are needed.

        Args:
            user_prompt: The original user prompt

        Returns:
            Dictionary indicating which tools might be needed
        """
        user_prompt_lower = user_prompt.lower()

        # Keywords that suggest filesystem operations
        filesystem_keywords = [
            "file",
            "directory",
            "folder",
            "read",
            "write",
            "list",
            "scan",
            "find",
            "search in",
            "look in",
            "contents of",
            "show me",
            "show files",
            "show directory",
            "browse",
        ]

        # Keywords that suggest web search operations
        web_search_keywords = [
            "search",
            "find on web",
            "find on internet",
            "google",
            "look up",
            "research",
            "latest news",
            "what is happening",
            "current",
            "recent",
            "today",
            "weather",
            "news",
            "fact check",
            "find information",
            "research about",
            "get info about",
        ]

        # Determine which tools might be needed
        needs_filesystem = any(
            keyword in user_prompt_lower for keyword in filesystem_keywords
        )
        needs_web_search = any(
            keyword in user_prompt_lower for keyword in web_search_keywords
        )

        # Log the analysis for debugging
        self.logger.info(
            f"Intent analysis - Filesystem: {needs_filesystem}, Web Search: {needs_web_search}, Prompt: {user_prompt[:100]}..."
        )

        return {
            "filesystem": needs_filesystem,
            "web_search": needs_web_search,
            "needs_tools": needs_filesystem or needs_web_search,
        }

    async def direct_model_response(self, prompt: str) -> str:
        """
        Get a direct response from the model without parallel thinking.
        """
        logger.info("Entering direct_model_response method.")

        # Ensure model server is running
        if not await self.model_manager.ensure_model_running():
            logger.error("Failed to ensure model server is running.")
            return "Error: Model server is not available."

        # Extract persona information from the complete context to use as system message
        # The complete context follows the sequence: PERSONA FOUNDATION, CONVERSATION HISTORY, CURRENT PROMPT, TOOL OUTPUTS
        if "PERSONA FOUNDATION:" in prompt:
            # Extract the persona information to use as system message
            persona_start = prompt.find("PERSONA FOUNDATION:") + len(
                "PERSONA FOUNDATION:"
            )
            persona_end = prompt.find("\n\n", persona_start)
            if (
                persona_end == -1
            ):  # If no next section marker, use to end of the persona part
                persona_part = prompt[persona_start:].strip()
            else:
                persona_part = prompt[persona_start:persona_end].strip()
        else:
            # Fallback to default system message if persona not found
            persona_part = "You are a helpful AI assistant. Provide a concise and accurate response to the user's query."

        # Prepare the messages for API call
        messages = [
            {"role": "system", "content": persona_part},
            {"role": "user", "content": prompt},
        ]

        # Use the updated configuration system to get the model
        active_provider = self.config_loader.get_active_provider()
        provider_config = self.config_loader.get_llm_config(active_provider)
        model_to_use = provider_config.get("model", "default-model")

        payload = {
            "model": model_to_use,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }

        # Use the API base from the model manager which may have been updated when starting a new model
        api_base = self.model_manager.api_base

        logger.info(f"Sending request to LLM API: {api_base}/chat/completions")
        try:
            async with self.http_client.post(
                f"{api_base}/chat/completions", json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("Received successful response from LLM API.")

                    # Extract the generated text
                    if "choices" in data and len(data["choices"]) > 0:
                        generated_text = data["choices"][0]["message"]["content"]
                        return generated_text
                    else:
                        raise Exception(f"Unexpected response format: {data}")
                else:
                    error_text = await response.text()
                    raise Exception(
                        f"API call failed with status {response.status}: {error_text}"
                    )
        except asyncio.TimeoutError:
            logger.error("Timeout error during LLM API call.")
            return "Error: Timeout after client session timeout."
        except aiohttp.ClientError as e:
            logger.error(f"Client error during LLM API call: {str(e)}")
            # Model might have gone down, try to restart
            await self.model_manager.ensure_model_running()
            return f"Error: {str(e)}"
        except Exception as e:
            logger.error(f"Generic error during LLM API call: {str(e)}")
            # Model might have gone down, try to restart
            await self.model_manager.ensure_model_running()
            return f"Error: {str(e)}"

    async def select_model(self, model_name: str) -> bool:
        """
        Select and start a specific model for on-demand execution.

        Args:
            model_name: Name of the model to select and start

        Returns:
            bool: True if model selected and started successfully, False otherwise
        """
        try:
            logger.info(f"Attempting to select model: {model_name}")

            # Use the model manager to select and start the model
            success = self.model_manager.select_model(model_name)

            if success:
                logger.info(f"Model {model_name} selected and started successfully")
                return True
            else:
                logger.error(f"Failed to select and start model: {model_name}")
                return False
        except Exception as e:
            logger.error(f"Error selecting model {model_name}: {str(e)}")
            return False

    async def get_available_models(self) -> list:
        """
        Get list of available models from the models directory.

        Returns:
            list: Available model information with name, size, quantization, etc.
        """
        try:
            logger.info("Retrieving available models")
            available_models = self.model_manager.get_available_models()
            logger.info(f"Found {len(available_models)} available models")
            return available_models
        except Exception as e:
            logger.error(f"Error retrieving available models: {str(e)}")
            return []

    async def get_current_model(self) -> str:
        """
        Get the currently active model.

        Returns:
            str: Current model name or None if no model is running
        """
        try:
            logger.info("Retrieving current model")
            current_model = self.model_manager.get_current_model()
            logger.info(f"Current model: {current_model}")
            return current_model
        except Exception as e:
            logger.error(f"Error retrieving current model: {str(e)}")
            return "Error retrieving current model"

    async def select_model(self, model_name: str) -> bool:
        """
        Select and start a specific model for on-demand execution.

        Args:
            model_name: Name of the model to select and start

        Returns:
            bool: True if model selected and started successfully, False otherwise
        """
        try:
            logger.info(f"Attempting to select model: {model_name}")

            # Use the model manager to select and start the model
            success = self.model_manager.select_model(model_name)

            if success:
                logger.info(f"Model {model_name} selected and started successfully")
                return True
            else:
                logger.error(f"Failed to select and start model: {model_name}")
                return False
        except Exception as e:
            logger.error(f"Error selecting model {model_name}: {str(e)}")
            return False

    async def get_model_status(self) -> dict:
        """
        Get the status of the model management system.

        Returns:
            dict: Status information about running models
        """
        try:
            logger.info("Retrieving model status")
            status = self.model_manager.get_model_status()
            logger.info(f"Model status: {status}")
            return status
        except Exception as e:
            logger.error(f"Error retrieving model status: {str(e)}")
            return {"error": f"Error retrieving model status: {str(e)}"}

    async def _ensure_utcp_client(self):
        """
        Ensure the UTCP client is initialized and ready to use.
        """
        if self.utcp_client is None:
            try:
                self.utcp_client = await UtcpClient.create(config=self.utcp_config)
                self.logger.info("UTCP client initialized successfully")
            except ImportError as e:
                self.logger.error(f"UTCP dependencies not available: {e}")
                self.logger.info(
                    "UTCP tools will not be available. To enable UTCP, install missing dependencies: pip install utcp utcp-http"
                )
                self.utcp_client = None  # Set to None to avoid repeated attempts
                return False
            except Exception as e:
                self.logger.error(f"Failed to initialize UTCP client: {e}")
                self.logger.error(traceback.format_exc())
                # Set to None to avoid repeated failed attempts
                self.utcp_client = None
                return False
        return True

    # Removed _evaluate_synthesis_quality method as it was part of the deprecated parallel thinking approach
    # The system now uses direct model calls and tool usage instead of synthesis from multiple thinkers

    async def initialize_utcp_client(self):
        try:
            if self.utcp_client is None:
                self.utcp_client = await UtcpClient.create(config=self.utcp_config)
            return True
        except ImportError as e:
            self.logger.error(f"UTCP dependencies not available: {e}")
            self.logger.info(
                "UTCP tools will not be available. To enable UTCP, install missing dependencies: pip install utcp utcp-http"
            )
            self.utcp_client = None  # Set to None to avoid repeated attempts
            return False
        except Exception as e:
            self.logger.error(f"Error initializing UTCP client: {e}")
            self.logger.error(traceback.format_exc())
            self.utcp_client = None  # Set to None to avoid repeated attempts
            return False

    async def cleanup(self):
        """
        Cleanup resources when the orchestrator agent is done.
        """
        # Close the HTTP client
        if hasattr(self, "http_client") and self.http_client:
            await self.http_client.close()

        # Close the UTCP client if it exists
        if hasattr(self, "utcp_client") and self.utcp_client:
            # UTCP client might have a close method depending on the implementation
            if hasattr(self.utcp_client, "close"):
                await self.utcp_client.close()

        # Shutdown model if needed
        if hasattr(self, "model_manager"):
            # Optionally shutdown the model if it's still running
            pass  # Let the model manager handle its own cleanup
