import httpx
import asyncio
import yaml
import os


class ConversationalAgent:
    def __init__(self, model: str = "gemma2:9b", api_base: str = None):
        self.model = model
        self.api_base = api_base
        self.system_prompt = (
            "You are a helpful AI assistant. Provide concise and relevant responses."
        )

    async def respond(self, prompt: str, system_prompt: str = None) -> str:
        # Use the custom system prompt if provided, otherwise use the default
        effective_system_prompt = (
            system_prompt if system_prompt is not None else self.system_prompt
        )

        print(f"  -> ConversationalAgent processing with model {self.model}...")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": effective_system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"num_gpu": 37},
        }

        if "ollama" in self.api_base:
            url = f"{self.api_base}/api/chat"
        else:
            url = f"{self.api_base}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                content = data.get("message", {}).get("content", "")
                return content

        except httpx.RequestError as e:
            error_message = f"HTTP request failed: {e.__class__.__name__} - {e}"
            print(f"Error in ConversationalAgent: {error_message}")
            return f"Error: {error_message}"
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(f"Error in ConversationalAgent: {error_message}")
            return f"Error: {error_message}"
