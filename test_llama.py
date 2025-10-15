import httpx
import asyncio
import json

async def test_llama_server():
    try:
        print("Testing connection to llama.cpp server...")
        async with httpx.AsyncClient() as client:
            # First, check if the server is responding to model listing
            models_response = await client.get('http://localhost:8080/v1/models', timeout=10.0)
            print("Models endpoint status:", models_response.status_code)
            if models_response.status_code == 200:
                print("Available models:", json.dumps(models_response.json(), indent=2))
            
            # Then try a simple chat completion
            result = await client.post(
                'http://localhost:8080/v1/chat/completions',
                json={
                    'model': 'jamba-reasoning-3b-F16.gguf',  # Using the model name from config
                    'messages': [{'role': 'user', 'content': 'Hello'}],
                    'max_tokens': 10,
                    'temperature': 0.7
                },
                timeout=30.0
            )
            print("Chat completion status:", result.status_code)
            if result.status_code == 200:
                response_data = result.json()
                print("Success! Response from LLM:", json.dumps(response_data, indent=2))
            else:
                print("Error response:", result.text)
    except Exception as e:
        print(f"Error connecting to llama.cpp server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llama_server())