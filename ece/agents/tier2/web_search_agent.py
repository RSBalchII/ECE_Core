import os
import httpx
import logging
from tavily import TavilyClient

class WebSearchAgent:
    def __init__(self, model: str, tavily_api_key: str = None):
        self.model = model
        # Use the provided API key, or fall back to environment variable
        self.tavily_client = TavilyClient(api_key=tavily_api_key or os.getenv("TAVILY_API_KEY"))
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

    async def search(self, query: str) -> str:
        print(f"WebSearchAgent searching for: '{query}'")
        try:
            search_results = self.tavily_client.search(query, search_depth="advanced")
            context = " ".join([result["content"] for result in search_results["results"]])

            prompt = f"Based on the following context, please answer the user's query.\n\nContext:\n{context}\n\nQuery:\n{query}"

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful AI assistant that answers questions based on web search results."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "num_gpu": 37
                }
            }

            url = f"{self.ollama_base_url}/api/chat"
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get('message', {}).get('content', '')

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {e.response.status_code} for URL {e.request.url}")
            return f"A web search error occurred (HTTP {e.response.status_code})."
        except httpx.RequestError as e:
            logging.error(f"Request error occurred: {e.__class__.__name__} for URL {e.request.url}")
            return "A web search error occurred (could not connect)."
        except Exception as e:
            logging.error(f"An unexpected error occurred during web search: {e}", exc_info=True)
            return "An unexpected error occurred during web search."
