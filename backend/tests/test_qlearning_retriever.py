
import unittest
from unittest.mock import patch, Mock

import importlib.util
from pathlib import Path

# Load the TODO/qlearning_retriever.py module by path so tests can run without package installs
spec = importlib.util.spec_from_file_location(
    "qlearning_retriever",
    str(Path(__file__).resolve().parents[1] / "TODO" / "qlearning_retriever.py")
)
qmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qmod)
QLearningGraphRetriever = qmod.QLearningGraphRetriever


class TestQLearningRetriever(unittest.TestCase):
    def setUp(self):
        # Build a retriever instance without invoking the real GraphDatabase.driver.
        # We'll attach a mocked driver/session to it directly.
        self.mock_driver = Mock()
        # Configure a session context manager
        self.session = Mock()

        class DummyCM:
            def __init__(self, s):
                self._s = s

            def __enter__(self):
                return self._s

            def __exit__(self, exc_type, exc, tb):
                return False

        self.mock_driver.session.return_value = DummyCM(self.session)

        # Create retriever object without calling __init__ and set attributes manually
        self.retriever = object.__new__(QLearningGraphRetriever)
        self.retriever.driver = self.mock_driver
        # Minimal attributes expected by methods
        from collections import defaultdict
        self.retriever.q_table = defaultdict(lambda: defaultdict(float))
        self.retriever.learning_rate = 0.1
        self.retriever.discount_factor = 0.9
        self.retriever.epsilon = 0.3
        self.retriever.max_hops = 3
        self.retriever.max_paths = 5

    def tearDown(self):
        pass

    def test_find_seed_entities_matches(self):
        # Mock DB result for seed search
        self.session.run.return_value = [{'id': 'e_sybil_name'}, {'id': 'e_other'}]

        ids = self.retriever.find_seed_entities('How about Sybil and other topics')
        self.assertEqual(ids, ['e_sybil_name', 'e_other'])

    def test_get_entities_data_prefers_display_name(self):
        # Mock DB records for _get_entities_data
        self.session.run.return_value = [
            {'id': 'e1', 'name': 'sybil', 'display_name': 'Sybil', 'type': 'person'}
        ]

        entities = self.retriever._get_entities_data(['e1'])
        self.assertEqual(len(entities), 1)
        e = entities[0]
        self.assertEqual(e['id'], 'e1')
        self.assertEqual(e['name'], 'sybil')
        self.assertEqual(e['display_name'], 'Sybil')
        self.assertEqual(e['preferred_name'], 'Sybil')


if __name__ == '__main__':
    unittest.main()
