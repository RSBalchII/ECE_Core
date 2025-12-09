import asyncio
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm import LLMClient


@pytest.mark.asyncio
async def test_long_text_embedding_chunked():
    llm = LLMClient()
    # If embeddings server not available, skip
    try:
        _ = await llm.detect_embeddings_model()
    except Exception:
        pytest.skip("Embeddings server not available")
    long_text = ' '.join(['word'] * 20000)
    # Prefer a small chunk_size to force multiple chunks and averaging
    emb_list = await llm.get_embeddings_for_documents([long_text], chunk_size=1024, batch_size=2, min_batch=1)
    assert emb_list is not None
    assert isinstance(emb_list, list)
    assert len(emb_list) == 1
    emb = emb_list[0]
    assert emb is not None
    assert isinstance(emb, list)
    assert len(emb) > 0
