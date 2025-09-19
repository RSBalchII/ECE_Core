# ece/agents/tier1/orchestrator/archivist_client.py
import httpx
from typing import List, Dict, Any

class ArchivistClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def get_context(self, query: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Get context from the Archivist agent.
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/context",
                json={"query": query, "keywords": keywords},
                timeout=30.0
            )
            if response.status_code == 200:
                return response.json().get("context", [])
            else:
                print(f"Archivist returned status {response.status_code}")
                return []
        except Exception as e:
            print(f"Error calling Archivist: {str(e)}")
            return []
