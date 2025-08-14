import uuid
from datetime import datetime

def create_memory_entry(content: str, source_type: str, source_identifier: str, original_timestamp_utc: str = None) -> dict:
    """
    Creates a single, robust Python function that is the heart of the ingestion process.
    """
    ingest_timestamp_utc = datetime.utcnow().isoformat() + "Z"
    # Correctly handle word count for strings with multiple spaces
    word_count = len(content.split())

    memory_entry = {
        "uuid": str(uuid.uuid4()),
        "content": content,
        "source_type": source_type,
        "source_identifier": source_identifier,
        "original_timestamp_utc": original_timestamp_utc,
        "ingest_timestamp_utc": ingest_timestamp_utc,
        "metadata": {
            "author": None,
            "summary": None,
            "keywords": [],
            "word_count": word_count
        },
        "version": "1.0"
    }
    return memory_entry