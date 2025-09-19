import httpx
import asyncio
import yaml
import os

class ConversationalAgent:
    def __init__(self, model: str = "gemma2:9b"):
        self.model = model
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.system_prompt = "You are a helpful AI assistant. Provide concise and relevant responses."

    async def respond(self, prompt: str) -> str:
        print(f"  -> ConversationalAgent processing with model {self.model}...")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{self.ollama_base_url}/api/chat", json=payload)
                response.raise_for_status()
                
                data = response.json()
                content = data.get('message', {}).get('content', '')
                return content

        except httpx.RequestError as e:
            error_message = f"HTTP request failed: {e.__class__.__name__} - {e}"
            print(f"Error in ConversationalAgent: {error_message}")
            return f"Error: {error_message}"
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(f"Error in ConversationalAgent: {error_message}")
            return f"Error: {error_message}"