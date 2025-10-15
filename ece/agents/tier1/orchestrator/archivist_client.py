# ece/agents/tier1/orchestrator/archivist_client.py
import httpx
import logging
from typing import List, Dict, Any


class ArchivistClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
        self.logger = logging.getLogger(__name__)

    async def get_context(self, query: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Get context from the Archivist agent.
        """
        try:
            self.logger.info(f"Calling Archivist at {self.base_url}/context with query: {query[:100]}...")
            response = await self.client.post(
                f"{self.base_url}/context",
                json={"query": query, "keywords": keywords},
                timeout=30.0
            )
            if response.status_code == 200:
                context_data = response.json().get("context", [])
                self.logger.info(f"Received {len(context_data)} context items from Archivist")
                return context_data
            else:
                self.logger.error(f"Archivist returned status {response.status_code}")
                return []
        except Exception as e:
            self.logger.error(f"Error calling Archivist: {str(e)}")
            return []

    async def get_enhanced_context(self, context_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get enhanced context from the Archivist agent, which coordinates with the QLearning Agent.
        
        Args:
            context_request: Dictionary containing query, keywords, max_tokens, and session_id
            
        Returns:
            Dictionary with enhanced_context and related_memories
        """
        try:
            self.logger.info(f"Calling Archivist at {self.base_url}/enhanced_context with query: {context_request.get('query', '')[:100]}...")
            response = await self.client.post(
                f"{self.base_url}/enhanced_context",
                json=context_request,
                timeout=60.0
            )
            if response.status_code == 200:
                enhanced_context_data = response.json()
                self.logger.info(f"Received enhanced context from Archivist: {len(enhanced_context_data.get('enhanced_context', ''))} characters")
                return enhanced_context_data
            else:
                self.logger.error(f"Archivist returned status {response.status_code}")
                return {}
        except Exception as e:
            self.logger.error(f"Error calling Archivist for enhanced context: {str(e)}")
            return {}

    async def query_memory(self, query: str) -> str:
        """
        Query the knowledge graph for relevant memory/context.
        
        Args:
            query: The query to search for in the knowledge graph
            
        Returns:
            A string containing relevant context from the knowledge graph
        """
        try:
            self.logger.info(f"Calling Archivist at {self.base_url}/query_memory with query: {query[:100]}...")
            response = await self.client.post(
                f"{self.base_url}/query_memory",
                json={"query": query},
                timeout=30.0
            )
            if response.status_code == 200:
                result = response.json()
                # Return the context content
                context_content = result.get("context", "") if isinstance(result, dict) else str(result)
                self.logger.info(f"Received context from Archivist: {len(context_content)} characters")
                return context_content
            else:
                self.logger.error(f"Archivist returned status {response.status_code}")
                return ""
        except Exception as e:
            self.logger.error(f"Error calling Archivist for query_memory: {str(e)}")
            return ""