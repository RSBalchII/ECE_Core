import pytest
from src.content_utils import is_token_soup, sanitize_token_soup


def test_is_token_soup_with_normal_text():
    text = "This is a clean human-readable summary with normal sentences. Nothing to see here."
    assert is_token_soup(text) is False


def test_is_token_soup_with_code_like_text():
    text = "memcpy(dest, src, size); manualHeaderValue=0x1F4A9; 0xffeeddccbbaa9900 7090 12345678 90abcdef; func_call(arg1, arg2);"
    assert is_token_soup(text) is True


def test_sanitize_token_soup_removes_code_and_hex():
    text = "Here is some code: memcpy(dest,src,size); 0xDEADBEEF; {\"response_content\": \"ignored\"} and valid words."
    s = sanitize_token_soup(text)
    assert "memcpy" not in s
    assert "0xDEADBEEF" not in s
    # still preserves readable words
    assert "valid words" in s
