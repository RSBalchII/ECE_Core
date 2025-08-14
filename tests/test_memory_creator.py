import pytest
import uuid
from datetime import datetime
from chimaera.injector.memory_creator import create_memory_entry

def test_create_memory_entry_happy_path():
    content = "This is some test content."
    source_type = "document"
    source_identifier = "doc_123"
    original_timestamp_utc = "2023-01-01T12:00:00Z"

    entry = create_memory_entry(content, source_type, source_identifier, original_timestamp_utc)

    assert isinstance(entry['uuid'], str)
    assert uuid.UUID(entry['uuid'], version=4)
    assert entry['content'] == content
    assert entry['source_type'] == source_type
    assert entry['source_identifier'] == source_identifier
    assert entry['original_timestamp_utc'] == original_timestamp_utc
    assert isinstance(entry['ingest_timestamp_utc'], str)
    assert datetime.fromisoformat(entry['ingest_timestamp_utc'].replace('Z', '+00:00'))
    assert entry['metadata']['author'] is None
    assert entry['metadata']['summary'] is None
    assert entry['metadata']['keywords'] == []
    assert entry['metadata']['word_count'] == len(content.split())
    assert entry['version'] == "1.0"

def test_create_memory_entry_minimal_path():
    content = "Minimal content."
    source_type = "log"
    source_identifier = "log_abc"

    entry = create_memory_entry(content, source_type, source_identifier)

    assert isinstance(entry['uuid'], str)
    assert uuid.UUID(entry['uuid'], version=4)
    assert entry['content'] == content
    assert entry['source_type'] == source_type
    assert entry['source_identifier'] == source_identifier
    assert entry['original_timestamp_utc'] is None
    assert isinstance(entry['ingest_timestamp_utc'], str)
    assert datetime.fromisoformat(entry['ingest_timestamp_utc'].replace('Z', '+00:00'))
    assert entry['metadata']['author'] is None
    assert entry['metadata']['summary'] is None
    assert entry['metadata']['keywords'] == []
    assert entry['metadata']['word_count'] == len(content.split())
    assert entry['version'] == "1.0"

def test_create_memory_entry_schema_validation():
    content = "Schema validation test."
    source_type = "test"
    source_identifier = "test_id"

    entry = create_memory_entry(content, source_type, source_identifier)

    expected_keys = [
        "uuid",
        "content",
        "source_type",
        "source_identifier",
        "original_timestamp_utc",
        "ingest_timestamp_utc",
        "metadata",
        "version"
    ]
    assert all(key in entry for key in expected_keys)
    assert isinstance(entry["metadata"], dict)
    assert "author" in entry["metadata"]
    assert "summary" in entry["metadata"]
    assert "keywords" in entry["metadata"]
    assert "word_count" in entry["metadata"]

def test_create_memory_entry_word_count():
    test_cases = [
        ("", 0),
        ("one", 1),
        ("one two three", 3),
        ("  leading and trailing spaces  ", 4),
        ("multiple    spaces    between    words", 4),
        ("Newnlinesrnandttabs", 1)
    ]

    for content, expected_count in test_cases:
        entry = create_memory_entry(content, "test", "wc_test")
        assert entry['metadata']['word_count'] == expected_count
