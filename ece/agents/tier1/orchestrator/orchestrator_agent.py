# chimaera-multi-modal-agent/external-context-engine-ece/chimaera-multi-modal-agent-External-Context-Engine-ECE-ee846bf46a8b6dcc81b49745ae692aeb515fc40d/ece/agents/tier1/orchestrator/orchestrator_agent.py
"""
Orchestrator Agent for the External Context Engine (ECE) v2.0 (Async).

This module implements the core logic for the Orchestrator agent using a fully
asynchronous model to align with the FastAPI server and enable non-blocking I/O.
"""

import os
import httpx
import asyncio
import yaml
import traceback
import logging
import typing
import uuid
from typing import Optional, Dict, Any, List
from xml.etree import ElementTree as ET
from urllib.parse import urlparse

from ece.agents.tier2.conversational_agent import ConversationalAgent
from ece.agents.tier2.explorer_agent import ExplorerAgent
from ece.agents.tier2.critique_agent import CritiqueAgent
from ece.agents.tier2.web_search_agent import WebSearchAgent
from ece.common.sandbox import run_code_in_sandbox
from ece.components.context_cache.cache_manager import CacheManager
from ece.agents.tier1.orchestrator.archivist_client import ArchivistClient


class BaseThinker:
    def __init__(self, name="Default", model=None, semaphore: asyncio.Semaphore = None):
        self.name = name
        self.model = model
        self.semaphore = semaphore
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.system_prompt = f"You are a helpful AI assistant acting as the '{self.name}' Thinker. Provide a concise analysis from this specific perspective."


    async def think(self, prompt: str) -> str:
        if not self.semaphore:
            raise ValueError("Semaphore not provided to BaseThinker")

        async with self.semaphore:
            print(f"  -> {self.name} Thinker processing with model {self.model}...")
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            url = f"{self.ollama_base_url}/api/chat"

            try:
                async with httpx.AsyncClient(timeout=1800.0) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()

                    data = response.json()
                    content = data.get('message', {}).get('content', '')

                    # Wrap the response in POML format
                    return f"<poml><perspective thinker='{self.name}'><analysis>{content}</analysis></perspective>"

            except httpx.HTTPStatusError as e:
                error_message = f"HTTP error occurred: {e.response.status_code} for URL {e.request.url}"
                logging.error(f"Error in {self.name} Thinker: {error_message}")
                return f"<poml><perspective thinker='{self.name}'><analysis>Error: {error_message}</analysis></perspective>"
            except httpx.RequestError as e:
                error_message = f"Request error occurred: {e.__class__.__name__} for URL {e.request.url}"
                logging.error(f"Error in {self.name} Thinker: {error_message}")
                return f"<poml><perspective thinker='{self.name}'><analysis>Error: {error_message}</analysis></perspective>"
            except Exception as e:
                error_message = f"An unexpected error occurred: {e}"
                logging.error(f"Error in {self.name} Thinker: {error_message}", exc_info=True)
                return f"<poml><perspective thinker='{self.name}'><analysis>Error: {error_message}</analysis></perspective>"


class SynthesisThinker(BaseThinker):
    def __init__(self, name="Synthesis", model=None, semaphore: asyncio.Semaphore = None):
        super().__init__(name, model, semaphore)
        self.system_prompt = "You are a master synthesizer. Your job is to take multiple, diverse perspectives on a topic and combine them into a single, coherent, and easy-to-read final analysis."

    async def think(self, prompt: str) -> str:
        if not self.semaphore:
            raise ValueError("Semaphore not provided to SynthesisThinker")

        async with self.semaphore:
            print(f"  -> {self.name} Thinker processing with model {self.model}...")
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            url = f"{self.ollama_base_url}/api/chat"

            try:
                async with httpx.AsyncClient(timeout=1800.0) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()

                    data = response.json()
                    # The final synthesis does not need to be wrapped in POML
                    return data.get('message', {}).get('content', '')

            except httpx.HTTPStatusError as e:
                error_message = f"HTTP error occurred: {e.response.status_code} for URL {e.request.url}"
                logging.error(f"Error in {self.name} Thinker: {error_message}")
                return f"Error during synthesis: {error_message}"
            except httpx.RequestError as e:
                error_message = f"Request error occurred: {e.__class__.__name__} for URL {e.request.url}"
                logging.error(f"Error in {self.name} Thinker: {error_message}")
                return f"Error during synthesis: {error_message}"
            except Exception as e:
                error_message = f"An unexpected error occurred: {e}"
                logging.error(f"Error in {self.name} Thinker: {error_message}", exc_info=True)
                return f"An unexpected error occurred during synthesis: {e}"

def get_all_thinkers(config, semaphore):
    thinker_model = config.get('ThinkerAgent', {}).get('model')
    thinker_personas = config.get('ThinkerAgent', {}).get('personas', [])
    return [BaseThinker(name, model=thinker_model, semaphore=semaphore) for name in thinker_personas]


class OrchestratorAgent:
    def __init__(self, session_id: str):
        print(f"DEBUG: TAVILY_API_KEY from os.getenv: {os.getenv('TAVILY_API_KEY')}")
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)

        self.session_id = session_id
        self.client = httpx.AsyncClient(timeout=60.0)
        self.llm_semaphore = asyncio.Semaphore(1)

        # --- REFACTORED: Initialize agents based on the new config.yaml structure ---
        llm_model = self.config.get('llm', {}).get('config', {}).get('model')
        synthesis_model = self.config.get('ThinkerAgent', {}).get('synthesis_model', llm_model)

        self.thinkers = get_all_thinkers(self.config, self.llm_semaphore)
        self.synthesis_thinker = SynthesisThinker(model=synthesis_model, semaphore=self.llm_semaphore)

        self.conversational_agent = ConversationalAgent(model=llm_model)
        self.explorer_agent = ExplorerAgent(model=llm_model)
        self.critique_agent = CritiqueAgent(model=llm_model, success_threshold=0.8) # Using a default threshold
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.web_search_agent = WebSearchAgent(model=llm_model, tavily_api_key=tavily_api_key) # Updated initialization
        self.distiller_agent = ConversationalAgent(model=llm_model) # Placeholder

        # --- FIX: Initialize CacheManager with Redis connection details from config.yaml ---
        redis_url = self.config.get('cache', {}).get('redis_url', 'redis://localhost:6379')
        parsed_url = urlparse(redis_url)

        redis_host = parsed_url.hostname
        redis_port = parsed_url.port

        self.cache_manager = CacheManager(host=redis_host, port=redis_port)

        # --- FIX: Initialize ArchivistClient with the URL from config.yaml ---
        archivist_url = self.config.get('archivist', {}).get('url', 'http://archivist:8003')
        self.archivist_client = ArchivistClient(base_url=archivist_url)


    def _route_prompt(self, prompt: str) -> str:
        """
        Routes a prompt based on the decision tree in the config.
        """
        prompt_lower = prompt.lower().strip()
        decision_tree = self.config.get('OrchestraAgent', {}).get('decision_tree', [])

        # Check for intents based on keywords
        for intent_data in decision_tree:
            if intent_data['intent'] == 'Default': # Skip default for now
                continue
            for keyword in intent_data.get('keywords', []):
                if keyword.lower() in prompt_lower:
                    # The new config has a list of tools, not a single agent per intent
                    # For now, we'll just return the intent name
                    print(f"Routing based on keyword: '{keyword}' -> {intent_data['intent']}")
                    return intent_data['intent']

        # If nothing matches, use the default agent.
        print(f"No specific intent found. Routing to default agent: ConversationalAgent")
        return "ConversationalAgent"

    def _extract_keywords(self, prompt: str) -> List[str]:
        """
        Extracts keywords from a prompt.
        """
        stop_words = set(["a", "an", "the", "in", "on", "at", "for", "to", "of", "i", "you", "he", "she", "it", "we", "they", "what", "who", "when", "where", "why", "how"])
        words = prompt.lower().split()
        keywords = [word for word in words if word not in stop_words]
        return keywords

    async def _get_context(self, prompt: str) -> str:
        """
        Fetches context from the Archivist and stores it in the cache.
        """
        print("Fetching context from Archivist...")
        keywords = self._extract_keywords(prompt)
        context_response = await self.archivist_client.get_context(prompt, keywords)
        if context_response:
            # For simplicity, we'll just use the first context item.
            # A more advanced implementation could synthesize multiple contexts.
            context = context_response[0].get('context', '')
            self.cache_manager.store(f"{self.session_id}:last_context", context)
            return context
        return ""

    async def _handle_cache_query(self, prompt: str) -> str:
        """
        Handles queries related to the cache manager.
        """
        print("Handling cache query...")
        stats = self.cache_manager.get_statistics()
        # A more sophisticated implementation would use an LLM to generate a natural language response.
        # For now, we'll return a formatted string.
        response = f"Cache Statistics:\n- Hits: {stats.get('hits')}\n- Misses: {stats.get('misses')}\n- Total Requests: {stats.get('total_requests')}\n- Hit Rate: {stats.get('hit_rate'):.2%}"

        # You could also add logic to retrieve and show recent cache entries.
        return response

    async def process_prompt(self, prompt: str) -> str:
        """
        Processes the prompt with comprehensive error logging and restored thinking logic.
        """
        print(f"Orchestrator processing prompt: '{prompt[:100]}...'")

        try:
            context = await self._get_context(prompt)
            if context:
                prompt_with_context = f"Context: {context}\n\nUser prompt: {prompt}"
            else:
                prompt_with_context = prompt

            target_agent_name = self._route_prompt(prompt)
            print(f"Routing to: {target_agent_name}")

            if target_agent_name == "ConversationalAgent":
                response = await self.conversational_agent.respond(prompt_with_context)
                self.cache_manager.store(f"{self.session_id}:last_prompt", prompt)
                self.cache_manager.store(f"{self.session_id}:last_response", response)
                return response

            elif target_agent_name == "Complex Reasoning":
                analysis_id = str(uuid.uuid4())
                asyncio.create_task(self._run_complex_reasoning(prompt, prompt_with_context, analysis_id))
                return f"I've started analyzing your request. This may take a moment. Your analysis ID is {analysis_id}."

            elif target_agent_name == "DistillerAgent":
                return await self.distiller_agent.respond(prompt)

            elif target_agent_name == "WebSearchAgent":
                return await self.web_search_agent.search(prompt)

            elif target_agent_name == "CacheManager":
                return await self._handle_cache_query(prompt)

            else:
                return f"Query received. Routed to {target_agent_name}. This agent is not yet fully integrated."

        except Exception as e:
            print(f"\n--- [!!!] ECE INTERNAL ERROR ---")
            print(f"Error occurred while processing prompt: '{prompt[:100]}...' ")
            traceback.print_exc()
            print(f"--- [!!!] END OF ERROR ---")
            raise e

    async def _run_complex_reasoning(self, original_prompt: str, prompt_with_context: str, analysis_id: str):
        perspectives_iterator = self._execute_parallel_thinking(prompt_with_context)
        final_response = await self._synthesize_parallel_response(original_prompt, perspectives_iterator)
        self.cache_manager.store(f"analysis:{analysis_id}", final_response)

    async def get_analysis_result(self, analysis_id: str) -> Optional[str]:
        return self.cache_manager.retrieve(f"analysis:{analysis_id}")

    async def _execute_parallel_thinking(self, prompt: str):
        print("Executing parallel thinking...")
        tasks = [asyncio.create_task(thinker.think(prompt)) for thinker in self.thinkers]
        
        for future in asyncio.as_completed(tasks):
            try:
                perspective = await future
                logging.info(f"Received perspective: {perspective}")
                yield perspective
            except Exception as e:
                # Find the thinker that caused the exception
                for i, task in enumerate(tasks):
                    if task == future:
                        thinker_name = self.thinkers[i].name
                        print(f"Error getting perspective from {thinker_name} Thinker: {e}")
                        yield f"<poml><perspective thinker='{thinker_name}'><analysis>Error: Could not generate perspective.</analysis></perspective></poml>"
                        break

    async def _synthesize_parallel_response(self, prompt: str, parallel_results: typing.AsyncIterator[str]) -> str:
        """
        This now constructs a final prompt and calls the SynthesisThinker.
        """
        print("Synthesizing parallel responses with a final LLM call...")

        synthesis_prompt = f"""Synthesize the following diverse perspectives into a single, final analysis. The original user query was: '{prompt}'.

--- Perspectives ---
"""
        async for perspective_poml in parallel_results:
            try:
                root = ET.fromstring(perspective_poml)
                thinker_name = root.find('.//perspective').get('thinker', 'Unknown')
                analysis = root.find('.//analysis')
                if analysis is not None and analysis.text:
                    synthesis_prompt += f"\n* {thinker_name}'s View: {analysis.text.strip()}"
            except ET.ParseError:
                continue # Skip unparseable perspectives

        logging.info(f"Synthesis prompt: {synthesis_prompt}")
        final_answer = await self.synthesis_thinker.think(synthesis_prompt)
        logging.info(f"Final answer: {final_answer}")
        return final_answer
