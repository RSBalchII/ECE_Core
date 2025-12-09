import os

files = {
    "requirements.txt": """# ECE_Core - Minimal Dependencies
fastapi==0.115.0
uvicorn==0.32.0
redis==5.2.0
httpx==0.28.1
openai==1.54.0
python-dotenv==1.1.1
pydantic==2.10.2
pydantic-settings==2.6.1
tiktoken==0.8.0
""",
    
    ".env.example": """# ECE_Core Configuration
REDIS_URL=redis://localhost:6379
REDIS_TTL=3600
NEO4J_URI=bolt://localhost:7687
NEO4J_HTTP=http://localhost:7474
LLM_API_BASE=http://localhost:8080/v1
LLM_MODEL=your-model-name
LLM_MAX_TOKENS=32000
ECE_HOST=127.0.0.1
ECE_PORT=8000
MAX_REDIS_TOKENS=8000
SUMMARIZE_THRESHOLD=6000
"""
}

for filename, content in files.items():
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created: {filename}")

print("\\nDone! Files created.")
