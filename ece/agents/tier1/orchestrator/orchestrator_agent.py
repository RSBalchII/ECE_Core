"""
Enhanced Orchestrator Agent with prompt management and stability improvements.
"""

import os
import httpx
import asyncio
import yaml
import traceback
import logging
from typing import Optional, Dict, Any, List
from xml.etree import ElementTree as ET
from urllib.parse import urlparse
import json

from ece.agents.tier2.conversational_agent import ConversationalAgent
from ece.agents.tier2.explorer_agent import ExplorerAgent
from ece.agents.tier2.critique_agent import CritiqueAgent
from ece.agents.tier2.web_search_agent import WebSearchAgent
from ece.common.sandbox import run_code_in_sandbox
from ece.components.context_cache.cache_manager import CacheManager
from ece.agents.tier1.orchestrator.archivist_client import ArchivistClient
from ece.common.prompt_manager import PromptManager, PromptConfig
from utcp.utcp_client import UtcpClient
from utcp.data.tool import Tool
from ece.agents.common.trm_client import TRMClient, TRMConfig
from ece.agents.common.markovian_thinker import MarkovianThinker, MarkovianConfig, ReasoningAnalyzer
from ece.agents.common.coordination_analyzer import ThinkerCoordinator

# Set up logging for the orchestrator
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseThinker:
    def __init__(self, name="Default", model=None, semaphore: asyncio.Semaphore = None, api_base: str = None, role_description: str = None):
        self.name = name
        self.model = model
        self.semaphore = semaphore
        self.api_base = api_base
        self.role_description = role_description or f"General thinker with perspective: {self.name}"
        
        # Assign persona based on name
        coordinator = ThinkerCoordinator()
        personas = coordinator.assign_thinker_personas()
        self.persona = personas.get(name, f"You are a helpful AI assistant acting as the '{self.name}' Thinker. Provide a concise analysis from this specific perspective.")
        
        self.system_prompt = self.persona

    async def think(self, prompt: str, other_thinkers_info: List[Dict[str, str]] = None) -> str:
        """
        Enhanced thinking method that includes ToM considerations.
        """
        if not self.semaphore:
            raise ValueError("Semaphore not provided to BaseThinker")

        # Generate ToM instructions if other thinkers are available
        to_m_instruction = ""
        if other_thinkers_info:
            coordinator = ThinkerCoordinator()
            to_m_instruction = coordinator.generate_thinker_instructions(self.name, other_thinkers_info)
            prompt = f"{to_m_instruction}\n\n{prompt}"

        async with self.semaphore:
            # Prepare the messages for API call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            try:
                # Make an async request to the configured LLM API
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        json={
                            "model": self.model,
                            "messages": messages,
                            "max_tokens": 1024,
                            "temperature": 0.7
                        }
                    )
                    
                    # Check if the request was successful
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Extract the generated text
                        if "choices" in data and len(data["choices"]) > 0:
                            generated_text = data["choices"][0]["message"]["content"]
                            return generated_text
                        else:
                            raise Exception(f"Unexpected response format: {data}")
                    else:
                        raise Exception(f"API call failed with status {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Error in thinker {self.name}: {str(e)}")
                return f"Error in {self.name} thinking: {str(e)}"


class SynthesisThinker(BaseThinker):
    def __init__(self, name="Synthesis", model=None, semaphore: asyncio.Semaphore = None, api_base: str = None, role_description: str = None):
        role_desc = role_description or "Combines insights from various specialized thinkers into a coherent, comprehensive response that addresses the original query while maintaining logical flow and internal consistency"
        super().__init__(name, model, semaphore, api_base, role_desc)
        self.system_prompt = "You are a Synthesis Thinker. Your role is to combine insights from various specialized thinkers into a coherent, comprehensive response that addresses the original query while maintaining logical flow and internal consistency."


def get_all_thinkers(config, semaphore, api_base):
    thinker_model = config.get('ThinkerAgent', {}).get('model')
    thinker_personas = config.get('ThinkerAgent', {}).get('personas', [])
    
    # If no personas are defined in config, use default personas
    if not thinker_personas:
        coordinator = ThinkerCoordinator()
        default_personas = coordinator.assign_thinker_personas()
        
        for name, persona_desc in default_personas.items():
            thinker_personas.append({
                'name': name.replace('Thinker', ''),  # Remove 'Thinker' suffix for config
                'system_prompt': persona_desc
            })

    thinkers = []
    for persona in thinker_personas:
        name = persona.get('name', 'Default')
        model = persona.get('model', thinker_model)
        system_prompt = persona.get('system_prompt', f"You are a helpful AI assistant acting as the '{name}' Thinker. Provide a concise analysis from this specific perspective.")
        
        # Properly handle the role description
        role_description = system_prompt.split('.')[0] if system_prompt else f"General {name} thinker"
        
        thinker = BaseThinker(
            name=name, 
            model=model, 
            semaphore=semaphore, 
            api_base=api_base,
            role_description=role_description
        )
        thinker.system_prompt = system_prompt
        thinkers.append(thinker)
    
    return thinkers


class EnhancedOrchestratorAgent:
    """
    Enhanced Orchestrator Agent with improved prompt management and stability features.
    """
    def __init__(self, session_id: str, config_path: str = 'config.yaml'):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize prompt manager for context overflow prevention
        llm_config = self.config.get('llm', {})
        provider_config = llm_config.get('providers', {}).get(llm_config.get('active_provider', 'ollama'), {})
        
        # Set max_tokens based on provider configuration
        max_tokens = 32768  # Default value
        if 'llama_cpp' in provider_config:
            # For llama.cpp, we might have specific context size in config
            max_tokens = 131072  # 128k as configured in our setup
        
        prompt_config = PromptConfig(
            max_tokens=max_tokens,
            reserved_tokens=1000,
            strategy="intelligent"
        )
        self.prompt_manager = PromptManager(prompt_config)
        
        self.session_id = session_id
        self.llm_semaphore = asyncio.Semaphore(1)
        
        # --- REFACTORED: Initialize agents based on the new config.yaml structure ---
        llm_config = self.config.get('llm', {})
        active_provider = llm_config.get('active_provider', 'ollama')
        provider_config = llm_config.get('providers', {}).get(active_provider, {})
        
        llm_model = provider_config.get('model', provider_config.get('model_path', 'default-model'))
        api_base = provider_config.get('api_base', 'http://localhost:11434/v1')
        
        synthesis_model = self.config.get('ThinkerAgent', {}).get('synthesis_model', llm_model)
        
        self.thinkers = get_all_thinkers(self.config, self.llm_semaphore, api_base)
        self.synthesis_thinker = SynthesisThinker(model=synthesis_model, semaphore=self.llm_semaphore, api_base=api_base)

        # Initialize other components
        archivist_url = self.config.get('archivist', {}).get('url', 'http://localhost:8003')
        self.archivist_client = ArchivistClient(base_url=archivist_url)
        self.cache_manager = CacheManager()
        
        # Store UTCP config for later initialization
        utcp_registry_url = os.getenv("UTCP_REGISTRY_URL", "http://localhost:8005")
        self.utcp_config = {
            "manual_call_templates": [{
                "name": "utcp_registry",
                "call_template_type": "http",
                "url": f"{utcp_registry_url}/utcp"  # Standard UTCP discovery endpoint
            }]
        }
        self.utcp_client = None  # Will be initialized when needed

        # Initialize TRM Client and Markovian Thinker
        trm_config = TRMConfig(
            api_base="http://localhost:8081/v1",  # Default TRM API base
            model="jamba-reasoning-3b-F16.gguf"   # TRM model
        )
        self.trm_client = TRMClient(trm_config)
        
        # Initialize Markovian Thinker with appropriate configuration
        markovian_config = MarkovianConfig(
            thinking_context_size=8192,  # 8K tokens per chunk
            markovian_state_size=4096,   # 4K tokens for carryover state
            iteration_cap=5,             # Max 5 chunks (allowing up to ~24K tokens total)
            temperature=0.6,             # Moderate temperature for consistency
            api_base=api_base,           # Use the same API base as other models
            model=llm_model              # Use the same model as configured
        )
        self.markovian_thinker = MarkovianThinker(markovian_config)

        # Initialize logger
        self.logger = logging.getLogger(__name__)

    async def process_prompt_with_context_management(self, user_prompt: str) -> str:
        """
        Process a prompt using context-aware management to prevent overflow.
        This method now implements the Markovian Thinking paradigm for complex prompts
        while falling back to parallel thinking for simpler ones.
        """
        try:
            # Analyze the prompt to decide which reasoning approach to use
            if ReasoningAnalyzer.should_use_markovian_thinking(user_prompt):
                self.logger.info("Using Markovian thinking for complex reasoning")
                return await self._process_with_markovian_thinking(user_prompt)
            else:
                self.logger.info("Using parallel thinking for simpler reasoning")
                # Get context from the knowledge graph via archivist
                context = await self.archivist_client.query_memory(user_prompt)
                
                # Use prompt manager to prepare the prompt safely
                prepared_prompt = self.prompt_manager.prepare_prompt(user_prompt, context)
                
                # Log context usage stats
                stats = self.prompt_manager.get_context_usage_stats(prepared_prompt)
                self.logger.info(f"Context usage stats: {json.dumps(stats, indent=2)}")
                
                if stats["over_limit"]:
                    self.logger.warning(f"Prompt was adjusted due to context overflow: {stats}")
                
                # Process the prepared prompt with parallel thinking
                result = await self.parallel_thinking(prepared_prompt)
                return result
                
        except Exception as e:
            self.logger.error(f"Error in process_prompt_with_context_management: {e}")
            self.logger.error(traceback.format_exc())
            return f"Error processing prompt: {str(e)}"
    
    async def _process_with_markovian_thinking(self, user_prompt: str) -> str:
        """
        Process a prompt using the Markovian Thinking paradigm as described in the research paper.
        This enables extremely long and complete reasoning by using fixed-size chunks
        with textual carryover state between chunks.
        """
        try:
            # Get context from the knowledge graph via archivist
            context = await self.archivist_client.query_memory(user_prompt)
            
            # Use the Markovian Thinker to process the prompt with chunked reasoning
            result = await self.markovian_thinker.markovian_reasoning_loop(
                initial_query=user_prompt,
                context=context
            )
            
            # Store the result in the cache for future reference
            self.cache_manager.store(f"{self.session_id}:markovian_result", result)
            
            self.logger.info(f"Markovian reasoning completed, result length: {len(result)} characters")
            return result
            
        except Exception as e:
            self.logger.error(f"Error in Markovian reasoning: {e}")
            self.logger.error(traceback.format_exc())
            # Fall back to parallel thinking if Markovian reasoning fails
            self.logger.info("Falling back to parallel thinking after Markovian reasoning failure")
            
            # Get context from the knowledge graph via archivist
            context = await self.archivist_client.query_memory(user_prompt)
            
            # Use prompt manager to prepare the prompt safely
            prepared_prompt = self.prompt_manager.prepare_prompt(user_prompt, context)
            
            # Process the prepared prompt with parallel thinking
            result = await self.parallel_thinking(prepared_prompt)
            return result

    async def parallel_thinking(self, prompt: str) -> str:
        """
        Perform parallel thinking with multiple specialized thinkers,
        incorporating coordination principles based on research findings.
        """
        # Get thinker roles and descriptions for ToM instructions
        thinker_info = [
            {"name": thinker.name, "role_description": getattr(thinker, 'role_description', 'General thinker')}
            for thinker in self.thinkers
        ]
        
        # Run coordinated thinking with ToM awareness
        thinker_tasks = [
            thinker.think(prompt, other_thinkers_info=thinker_info) 
            for thinker in self.thinkers
        ]
        thinker_results = await asyncio.gather(*thinker_tasks, return_exceptions=True)

        # Filter out any errors and prepare insights
        valid_insights = []
        for i, result in enumerate(thinker_results):
            if isinstance(result, Exception):
                logger.error(f"Error from thinker {i}: {result}")
                continue
            # Clean up the result from any POML tags before processing
            cleaned_result = result.replace("<poml>", "").replace("</poml>", "").replace("<perspective thinker='{}'>".format(self.thinkers[i].name), "").replace("</perspective>", "").replace("<analysis>", "").replace("</analysis>", "")
            valid_insights.append({
                "thinker_name": self.thinkers[i].name,
                "role_description": self.thinkers[i].role_description,
                "analysis": cleaned_result.strip()
            })

        # Combine all insights into a structured format for synthesis
        structured_insights = []
        for insight in valid_insights:
            structured_insights.append(
                f"Thinker: {insight['thinker_name']} ({insight['role_description']})\n"
                f"Analysis: {insight['analysis']}\n"
            )
        
        combined_insights = "\n".join(structured_insights)
        
        # Analyze coordination metrics
        try:
            from ece.agents.common.coordination_analyzer import CoordinationAnalyzer
            analyzer = CoordinationAnalyzer()
            
            # Extract just the results for analysis (before cleaning)
            results_only = [result for result in thinker_results if not isinstance(result, Exception)]
            if results_only:
                synergy = analyzer.measure_synergy(results_only)
                diversity = analyzer.measure_diversity(results_only)
                complementarity = analyzer.measure_complementarity(results_only, prompt)
                
                logger.info(f"Coordination metrics - Synergy: {synergy:.2f}, Diversity: {diversity:.2f}, Complementarity: {complementarity:.2f}")
        except Exception as e:
            logger.warning(f"Could not calculate coordination metrics: {e}")

        # Use synthesis thinker to create coherent response
        synthesis_prompt = f"""
        The following insights have been gathered from specialized thinkers with distinct roles. 
        Please synthesize these into a coherent, comprehensive response that addresses the original query.
        
        Original query: {prompt}
        
        Insights from different thinkers:
        {combined_insights}
        
        Please integrate the various perspectives into a unified response that:
        1. Addresses the core question/query
        2. Incorporates relevant insights from different thinker perspectives
        3. Maintains a natural, conversational flow
        4. Does not explicitly mention the names of the thinkers in the final response
        
        Synthesized response:
        """
        
        try:
            synthesis_result = await self.synthesis_thinker.think(synthesis_prompt, other_thinkers_info=[])
            
            # Quality control: Check if synthesis is occurring properly
            # If the result looks like concatenated responses (has multiple greetings), 
            # it may indicate that synthesis is not working correctly
            response_quality = self._evaluate_synthesis_quality(synthesis_result, valid_insights)
            
            if not response_quality['is_properly_synthesized']:
                logger.warning("Synthesis quality check failed - responses may not be properly integrated")
                logger.info(f"Quality metrics: {response_quality}")
            
            return synthesis_result
        except Exception as e:
            logger.error(f"Synthesis thinker failed: {e}")
            logger.error("Falling back to basic response generation")
            
            # Fallback response when synthesis fails
            fallback_response = "I analyzed this from multiple perspectives, but I'm unable to provide a detailed synthesis right now. How can I assist you further with your query?"
            return fallback_response

    async def handle_filesystem_request(self, path: str = ".") -> str:
        """
        Handle filesystem requests by discovering and calling appropriate UTCP tools.
        """
        try:
            # Initialize UTCP client if not already done
            if self.utcp_client is None:
                self.utcp_client = await UtcpClient.create(config=self.utcp_config)
            
            # Discover available filesystem tools via UTCP
            all_tools = await self.utcp_client.search_tools('', limit=100)  # Get all tools
            # Filter for filesystem tools
            fs_tools = [tool for tool in all_tools if 'filesystem' in tool.name.lower() or 'filesystem' in tool.tags]
            
            # Log available tools
            self.logger.info(f"Available filesystem tools: {[tool.name for tool in fs_tools]}")
            
            if not fs_tools:
                return "No filesystem tools available via UTCP"
            
            # Find and call appropriate tool
            for tool in fs_tools:
                if 'list' in tool.name.lower() or 'dir' in tool.name.lower():
                    result = await self.utcp_client.call_tool(tool.name, {"path": path})
                    return result
                elif 'read' in tool.name.lower():
                    # This would handle file reading
                    pass
            
            # If no specific tool found, use the first available
            if fs_tools:
                result = await self.utcp_client.call_tool(fs_tools[0].name, {"path": path})
                return result
            
            return "No suitable filesystem tool found"
            
        except Exception as e:
            self.logger.error(f"Error in handle_filesystem_request: {e}")
            self.logger.error(traceback.format_exc())
            return f"Error handling filesystem request: {str(e)}"

    async def handle_web_search_request(self, query: str) -> str:
        """
        Handle web search requests by discovering and calling appropriate UTCP tools.
        """
        try:
            # Initialize UTCP client if not already done
            if self.utcp_client is None:
                self.utcp_client = await UtcpClient.create(config=self.utcp_config)
            
            # Discover available web search tools via UTCP
            all_tools = await self.utcp_client.search_tools('', limit=100)  # Get all tools
            # Filter for web search tools
            web_tools = [tool for tool in all_tools if 'web' in tool.name.lower() or 'web' in tool.tags or 'search' in tool.name.lower()]
            
            # Log available tools
            self.logger.info(f"Available web search tools: {[tool.name for tool in web_tools]}")
            
            if not web_tools:
                return "No web search tools available via UTCP"
            
            # Find and call appropriate tool
            for tool in web_tools:
                if 'search' in tool.name.lower():
                    result = await self.utcp_client.call_tool(tool.name, {"query": query})
                    return result
            
            # If no search tool found, use the first available
            if web_tools:
                result = await self.utcp_client.call_tool(web_tools[0].name, {"query": query})
                return result
            
            return "No suitable web search tool found"
            
        except Exception as e:
            self.logger.error(f"Error in handle_web_search_request: {e}")
            self.logger.error(traceback.format_exc())
            return f"Error handling web search request: {str(e)}"

    def _evaluate_synthesis_quality(self, synthesis_result: str, original_insights: list) -> dict:
        """
        Evaluate if the synthesis properly integrated multiple perspectives or just concatenated them.
        
        Args:
            synthesis_result: The final synthesized response
            original_insights: List of original insights from different thinkers
            
        Returns:
            A dictionary with quality metrics and assessment
        """
        quality_metrics = {
            'is_properly_synthesized': True,
            'duplicate_content_detected': False,
            'greeting_count': 0,
            'has_integrated_elements': False
        }
        
        # Check if the synthesis contains multiple greetings (indicating poor synthesis)
        greeting_variations = [
            "hello", "hi ", "hey ", "greetings", "how can i", 
            "i'm here to", "let me", "first", "on one hand", "on the other hand",
            "in my opinion", "from my perspective"
        ]
        
        synthesis_lower = synthesis_result.lower()
        greeting_count = 0
        for greeting in greeting_variations:
            if greeting in synthesis_lower:
                greeting_count += synthesis_lower.count(greeting)
        
        quality_metrics['greeting_count'] = greeting_count
        
        # If we have more than 2 greetings, synthesis might be poor
        if greeting_count > 2:
            quality_metrics['is_properly_synthesized'] = False
        
        # Check for repetitive content or poor integration
        # If the synthesis is simply the original insights concatenated together
        insight_texts = [insight['analysis'].strip() for insight in original_insights]
        combined_original_length = sum(len(text) for text in insight_texts)
        
        # If the synthesis length is roughly the sum of all insights, it might be just concatenation
        if len(synthesis_result) > 0 and combined_original_length > 0:
            expansion_ratio = len(synthesis_result) / combined_original_length
            if expansion_ratio > 1.5:  # If it's much longer, it might be concatenation
                quality_metrics['duplicate_content_detected'] = True
                quality_metrics['is_properly_synthesized'] = False
        
        # Check if the synthesis shows evidence of integrating different perspectives
        integration_indicators = [
            "on the one hand", "on the other hand", "while", "however", "but", 
            "combining", "integrating", "balancing", "considering", "different"
        ]
        
        has_integration = any(indicator in synthesis_lower for indicator in integration_indicators)
        quality_metrics['has_integrated_elements'] = has_integration
        
        # Update the final assessment
        if has_integration and not quality_metrics['duplicate_content_detected']:
            quality_metrics['is_properly_synthesized'] = True
        
        return quality_metrics

    async def initialize_utcp_client(self):
        """
        Initialize the UTCP client with proper configuration.
        """
        try:
            # Initialize UTCP client if not already done
            if self.utcp_client is None:
                self.utcp_client = await UtcpClient.create(config=self.utcp_config)
            return True
        except Exception as e:
            self.logger.error(f"Error initializing UTCP client: {e}")
            self.logger.error(traceback.format_exc())
            return False