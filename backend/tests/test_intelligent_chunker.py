import pytest
from src.intelligent_chunker import IntelligentChunker


class FakeLLM:
    def __init__(self, response="A"):
        self.response = response

    async def generate(self, prompt, **kwargs):
        # Return the configured response; helpful to vary
        return self.response


@pytest.mark.asyncio
async def test_split_semantic_chunks_paragraphs():
    llm = FakeLLM()
    ch = IntelligentChunker(llm)
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = ch._split_semantic_chunks(text)
    assert len(chunks) == 1


@pytest.mark.asyncio
async def test_split_semantic_chunks_large_text():
    llm = FakeLLM()
    ch = IntelligentChunker(llm)
    # Create large text to force chunking (> chunk_size)
    long_para = "A" * (ch.chunk_size + 10)
    text = long_para + "\n\n" + long_para
    chunks = ch._split_semantic_chunks(text)
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_determine_strategy_short_confirmations():
    llm = FakeLLM("A")
    ch = IntelligentChunker(llm)
    strategy = await ch._determine_strategy("yes, agreed", "")
    assert strategy == "annotation_only"


@pytest.mark.asyncio
async def test_determine_strategy_code_block_is_full_detail():
    llm = FakeLLM("C")
    ch = IntelligentChunker(llm)
    strategy = await ch._determine_strategy("```\ndef foo(): pass```", "")
    assert strategy == "full_detail"


@pytest.mark.asyncio
async def test_process_chunk_annotation_only_calls_llm():
    llm = FakeLLM("Annotation result")
    ch = IntelligentChunker(llm)
    res = await ch._process_chunk("short yes text", 1, 1, "annotation_only")
    assert res["strategy"] == "annotation_only"
    assert "Annotation result" in res["content"]
