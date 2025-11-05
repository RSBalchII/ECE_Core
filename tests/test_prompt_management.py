"""
Unit tests for the prompt management and context overflow prevention in the ECE system.
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, MagicMock

from ece.common.prompt_manager import PromptManager, PromptConfig
from ece.common.token_utils import (
    count_tokens,
    truncate_text_to_tokens,
    split_text_by_tokens,
)
from ece.agents.tier1.orchestrator.orchestrator_agent import EnhancedOrchestratorAgent


class TestPromptManager(unittest.TestCase):
    """Test cases for the PromptManager class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = PromptConfig(
            max_tokens=2000, reserved_tokens=100, strategy="intelligent"
        )
        self.prompt_manager = PromptManager(self.config)

    def test_count_tokens(self):
        """Test the count_tokens method."""
        text = "This is a simple test sentence."
        token_count = self.prompt_manager.count_tokens(text)
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)

    def test_prepare_prompt_within_limit(self):
        """Test preparing a prompt that is within the token limit."""
        short_prompt = "This is a short prompt."
        result = self.prompt_manager.prepare_prompt(short_prompt)
        self.assertEqual(result, short_prompt)

    def test_prepare_prompt_with_context_within_limit(self):
        """Test preparing a prompt with context that is within the token limit."""
        short_prompt = "This is a short prompt."
        short_context = "This is a short context."
        result = self.prompt_manager.prepare_prompt(short_prompt, short_context)
        expected = f"{short_context}\n\n{short_prompt}"
        self.assertEqual(result, expected)

    def test_prepare_prompt_exceeds_limit_truncate_strategy(self):
        """Test preparing a prompt that exceeds the limit with truncate strategy."""
        # Create a long text that will exceed the limit
        long_text = "A " * 3000  # This should exceed our 1900 available tokens

        # Change the strategy to truncate for this test
        self.prompt_manager.config.strategy = "truncate"

        result = self.prompt_manager.prepare_prompt(long_text)

        # The result should be truncated
        result_token_count = self.prompt_manager.count_tokens(result)
        self.assertLessEqual(result_token_count, 1900)  # 2000 - 100 reserved

    def test_get_context_usage_stats(self):
        """Test getting context usage statistics."""
        text = "This is a test."
        stats = self.prompt_manager.get_context_usage_stats(text)

        self.assertIn("token_count", stats)
        self.assertIn("max_tokens", stats)
        self.assertIn("reserved_tokens", stats)
        self.assertIn("available_tokens", stats)
        self.assertIn("usage_percentage", stats)
        self.assertIn("over_limit", stats)


class TestTokenUtils(unittest.TestCase):
    """Test cases for the token utilities"""

    def test_count_tokens_single_string(self):
        """Test counting tokens in a single string."""
        text = "Hello, world!"
        token_count = count_tokens(text)
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)

    def test_count_tokens_list_of_strings(self):
        """Test counting tokens in a list of strings."""
        texts = ["Hello, ", "world!"]
        token_count = count_tokens(texts)
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)

    def test_truncate_text_to_tokens(self):
        """Test truncating text to a specific number of tokens."""
        long_text = "A " * 100  # Create a long text
        truncated = truncate_text_to_tokens(long_text, 10)  # Truncate to 10 tokens
        truncated_token_count = count_tokens(truncated)

        self.assertLessEqual(truncated_token_count, 10)

    def test_split_text_by_tokens(self):
        """Test splitting text into chunks by token count."""
        long_text = "A " * 50  # Create a moderately long text
        chunks = split_text_by_tokens(long_text, 10)  # Split into chunks of 10 tokens

        # Should have multiple chunks
        self.assertGreater(len(chunks), 1)

        # Each chunk (except possibly the last) should be close to the target token count
        for i, chunk in enumerate(chunks[:-1]):  # Exclude the last chunk
            chunk_token_count = count_tokens(chunk)
            self.assertLessEqual(chunk_token_count, 10)


class TestEnhancedOrchestratorAgent(unittest.IsolatedAsyncioTestCase):
    """Test cases for the EnhancedOrchestratorAgent"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create an orchestrator with a mock config
        self.mock_config = {
            "llm": {
                "active_provider": "llama_cpp",
                "providers": {
                    "llama_cpp": {
                        "model_path": "./models/test_model.gguf",
                        "api_base": "http://localhost:8080/v1",
                    }
                },
            },
            "cache": {"redis_url": "redis://localhost:6379"},
            "archivist": {"url": "http://localhost:8003"},
            "OrchestraAgent": {
                "decision_tree": [
                    {"intent": "TestIntent", "keywords": ["test", "hello"]}
                ]
            },
            "ThinkerAgent": {
                "model": "test-model",
                "personas": ["TestThinker"],
                "synthesis_model": "test-synthesis-model",
            },
        }

        # Mock file operations
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=str(self.mock_config))
        ):
            with patch("yaml.safe_load", return_value=self.mock_config):
                with patch(
                    "ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.__init__",
                    return_value=None,
                ):
                    with patch(
                        "ece.components.context_cache.cache_manager.CacheManager.__init__",
                        return_value=None,
                    ):
                        with patch(
                            "utcp_client.client.UTCPClient.__init__", return_value=None
                        ):
                            self.orchestrator = EnhancedOrchestratorAgent(
                                session_id="test-session"
                            )

    @patch(
        "ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.get_context",
        new_callable=MagicMock,
    )
    async def test_process_prompt_with_context_management(self, mock_get_context):
        """Test that the orchestrator processes prompts with context management."""
        # Mock the archivist client to return some context
        mock_get_context.return_value = [{"context": "This is a test context"}]

        # Test with a normal prompt
        result = await self.orchestrator.process_prompt("This is a test prompt")

        # The result should be a string (the response)
        self.assertIsInstance(result, str)

        # The prompt should have been processed without errors
        self.assertGreater(len(result), 0)

    @patch(
        "ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.get_context",
        new_callable=MagicMock,
    )
    async def test_process_prompt_with_long_input(self, mock_get_context):
        """Test that the orchestrator handles long prompt inputs correctly."""
        # Mock the archivist client to return some context
        mock_get_context.return_value = [{"context": "This is a test context"}]

        # Create a long prompt that would exceed typical context limits
        long_prompt = "This is a very long prompt. " * 1000

        # The orchestrator should handle this without crashing
        result = await self.orchestrator.process_prompt(long_prompt)

        # The result should be a string (the response)
        self.assertIsInstance(result, str)

        # The prompt should have been processed without errors
        self.assertGreater(len(result), 0)


if __name__ == "__main__":
    unittest.main()
