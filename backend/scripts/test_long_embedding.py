import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
import os
# Ensure test hits the embeddings-only server by default
os.environ.setdefault('LLM_EMBEDDINGS_API_BASE', 'http://127.0.0.1:8081/v1')
os.environ.setdefault('LLM_EMBEDDINGS_LOCAL_FALLBACK_ENABLED', 'false')
# For testing smaller model context sizes (e.g., 8k tokens), allow overriding via environment variable.
os.environ.setdefault('LLM_CONTEXT_SIZE', '8192')
from src.llm import LLMClient
from src.config import settings

async def test_long():
    c = LLMClient()
    long_text = ' '.join(['word']*20000)
    try:
        print(f"Using API base: {c.api_base}, Embeddings base: {c.embeddings_base}")
        print(f"Embedding backoff sequence: {settings.llm_embeddings_chunk_backoff_sequence}")
        # Print detected embeddings model context and computed chunk size for debugging
        detected_model = await c.detect_embeddings_model()
        detected_ctx = getattr(c, '_detected_server_context_size', None)
        print(f"Detected embeddings model: {detected_model}; context_tokens: {detected_ctx}")
        chars_per_token = getattr(settings, 'llm_chars_per_token', 4)
        ratio = getattr(settings, 'llm_chunk_context_ratio', 0.5)
        if detected_ctx:
            tokens_per_chunk = max(64, int(detected_ctx * ratio))
            computed_chunk_chars = int(tokens_per_chunk * chars_per_token)
            computed_chunk_chars = min(getattr(settings, 'llm_embeddings_chunk_size_default', 4096), computed_chunk_chars)
            print(f"Computed chunk chars: {computed_chunk_chars} (tokens_per_chunk={tokens_per_chunk})")
        batch = getattr(settings, 'llm_embeddings_default_batch_size', 4)
        emb = await c.get_embeddings_for_documents([long_text], batch_size=batch)
        print('Got', 'None' if not emb or emb[0] is None else 'embedding len='+str(len(emb[0])))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_long())
