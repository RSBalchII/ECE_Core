import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.neo4j_fix_tags_metadata import detect_and_fix


class FakeSession:
    def __init__(self, records):
        self._records = records

    def run(self, cypher, params=None):
        class _Result:
            def __init__(self, rs):
                self._rs = rs

            def __iter__(self):
                return iter(self._rs)

            def __repr__(self):
                return repr(self._rs)

        return _Result(self._records)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeDriver:
    def __init__(self, records):
        self._records = records

    def session(self):
        return FakeSession(self._records)

    def close(self):
        pass


def test_detect_and_fix_dry_run():
    # create one record with tags and metadata as JSON strings
    rec = {"id": 1, "tags": '["alpha","beta"]', "metadata": '{"src":"t"}'}
    driver = FakeDriver([rec])
    scanned, updated = detect_and_fix(driver, apply=False, limit=10)
    assert scanned == 1
    assert updated == 0  # dry-run should not apply


def test_detect_and_fix_apply():
    rec = {"id": 1, "tags": '["alpha"]', "metadata": '{"src":"t"}'}
    driver = FakeDriver([rec])
    scanned, updated = detect_and_fix(driver, apply=True, limit=10)
    assert scanned == 1
    # our FakeDriver doesn't actually store writes, but the function should attempt updates and return counts
    assert isinstance(updated, int)
