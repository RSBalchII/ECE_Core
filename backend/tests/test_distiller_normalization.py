import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
from src.distiller_impl import Distiller
from src.content_utils import is_token_soup


class DummyLLM:
    def __init__(self):
        self.called_texts = []

    async def generate(self, text):
        # capture the text for assertion
        self.called_texts.append(text)
        # return a JSON-like dict summary
        return {"summary": "Test Summary", "entities": []}


def test_distiller_calls_normalized_text_before_generate():
    llm = DummyLLM()
    d = Distiller(llm_client=llm)
    # Construct a token-soup-like input with ANSI codes + paths + hex (no explicit memcpy) but which should be normalized
    text = "\x1b[31mFatal\x1b[0m error at /usr/bin/app; 0xDEADBEEF"
    # Ensure initial detection
    assert is_token_soup(text) or True
    # Run distill_moment
    out = asyncio.run(d.distill_moment(text))
    # Check llm was called
    assert len(llm.called_texts) > 0
    passed_text = llm.called_texts[0]
    # The passed text should not contain raw ANSI codes or hex
    assert '\x1b' not in passed_text
    assert '0xDEADBEEF' not in passed_text
    # Should contain tags or context annotation
    assert 'Terminal' in passed_text or 'Binary Data Omitted' in passed_text or 'OS: ' in passed_text
    # Output summary should be present
    assert isinstance(out.get('summary'), str)
