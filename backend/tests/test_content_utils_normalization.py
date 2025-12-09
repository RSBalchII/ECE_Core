import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.content_utils import normalize_technical_content, contains_ansi_codes, contains_unix_path, contains_windows_path, contains_hex_dump


def test_ansi_normalization():
    s = "Error \x1b[31mFailed\x1b[0m: something went wrong"
    normalized = normalize_technical_content(s)
    assert '[Context: Terminal Output]' in normalized
    assert 'Failed' in normalized
    assert '\x1b' not in normalized


def test_windows_path_annotation():
    s = "C:\\Program Files\\Example\\bin\\exec.exe failed"
    normalized = normalize_technical_content(s)
    assert '[OS: Windows]' in normalized
    assert 'C:' in normalized


def test_unix_path_annotation():
    s = "/usr/bin/python3: error converting file"
    normalized = normalize_technical_content(s)
    assert '[OS: Linux]' in normalized
    assert '/usr/bin' in normalized


def test_hexdump_annotation():
    s = "00000000: 48 65 6C 6C 6F 20 57 6F 72 6C 64"
    normalized = normalize_technical_content(s)
    assert '[Binary Data Omitted]' in normalized or '[binary_data]' in normalized
