"""
Integration tests for the prompt management and stability enhancements in the ECE system.
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, MagicMock

from ece.common.prompt_manager import PromptManager, PromptConfig
from ece.agents.tier1.orchestrator.orchestrator_agent import EnhancedOrchestratorAgent


class TestPromptManagementIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for the prompt management system"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = {
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
                    {
                        "intent": "ConversationalAgent",
                        "keywords": ["hello", "hi", "help"],
                    }
                ]
            },
            "ThinkerAgent": {
                "model": "test-model",
                "personas": ["TestThinker"],
                "synthesis_model": "test-synthesis-model",
            },
        }

    @patch("builtins.open")
    @patch("yaml.safe_load")
    @patch("ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.__init__")
    @patch("ece.components.context_cache.cache_manager.CacheManager.__init__")
    @patch("utcp_client.client.UTCPClient.__init__")
    @patch("ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.get_context")
    @patch("ece.agents.tier2.conversational_agent.ConversationalAgent.respond")
    async def test_full_prompt_processing_pipeline(
        self,
        mock_conversation_respond,
        mock_get_context,
        mock_utcp_client,
        mock_cache_manager,
        mock_archivist_client,
        mock_yaml_load,
        mock_open,
    ):
        """Test the full prompt processing pipeline with context management."""
        # Set up the mocks
        mock_open.return_value.__enter__.return_value.read.return_value = str(
            self.config
        )
        mock_yaml_load.return_value = self.config
        mock_archivist_client.return_value = None
        mock_cache_manager.return_value = None
        mock_utcp_client.return_value = None
        mock_get_context.return_value = [
            {"context": "This is a test context for the integration"}
        ]
        mock_conversation_respond.return_value = (
            "This is a test response from the conversational agent."
        )

        # Create the orchestrator
        orchestrator = EnhancedOrchestratorAgent(session_id="test-session")

        # Process a prompt through the full pipeline
        result = await orchestrator.process_prompt("Hello, how are you?")

        # Verify the result
        self.assertIsInstance(result, str)
        self.assertIn("test response", result.lower())

        # Verify the correct methods were called
        mock_get_context.assert_called_once()
        mock_conversation_respond.assert_called_once()

    @patch("builtins.open")
    @patch("yaml.safe_load")
    @patch("ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.__init__")
    @patch("ece.components.context_cache.cache_manager.CacheManager.__init__")
    @patch("utcp_client.client.UTCPClient.__init__")
    @patch("ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.get_context")
    @patch("ece.agents.tier2.conversational_agent.ConversationalAgent.respond")
    async def test_prompt_truncation_integration(
        self,
        mock_conversation_respond,
        mock_get_context,
        mock_utcp_client,
        mock_cache_manager,
        mock_archivist_client,
        mock_yaml_load,
        mock_open,
    ):
        """Test that the system properly handles prompt truncation."""
        # Set up the mocks
        mock_open.return_value.__enter__.return_value.read.return_value = str(
            self.config
        )
        mock_yaml_load.return_value = self.config
        mock_archivist_client.return_value = None
        mock_cache_manager.return_value = None
        mock_utcp_client.return_value = None

        # Create a very long context that would require truncation
        long_context = [{"context": "This is a very long context. " * 5000}]
        mock_get_context.return_value = long_context
        mock_conversation_respond.return_value = "Response to truncated prompt."

        # Create the orchestrator
        orchestrator = EnhancedOrchestratorAgent(session_id="test-session")

        # Process a prompt that combined with context would exceed limits
        long_prompt = "This is a long prompt. " * 1000
        result = await orchestrator.process_prompt(long_prompt)

        # Verify the result
        self.assertIsInstance(result, str)
        self.assertIn("Response", result)

        # The system should have handled the long prompt without errors
        mock_conversation_respond.assert_called_once()

    @patch("builtins.open")
    @patch("yaml.safe_load")
    @patch("ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.__init__")
    @patch("ece.components.context_cache.cache_manager.CacheManager.__init__")
    @patch("utcp_client.client.UTCPClient.__init__")
    @patch("ece.agents.tier1.orchestrator.archivist_client.ArchivistClient.get_context")
    async def test_error_handling_in_prompt_processing(
        self,
        mock_get_context,
        mock_utcp_client,
        mock_cache_manager,
        mock_archivist_client,
        mock_yaml_load,
        mock_open,
    ):
        """Test that the system handles errors gracefully."""
        # Set up the mocks
        mock_open.return_value.__enter__.return_value.read.return_value = str(
            self.config
        )
        mock_yaml_load.return_value = self.config
        mock_archivist_client.return_value = None
        mock_cache_manager.return_value = None
        mock_utcp_client.return_value = None

        # Make the archivist client raise an exception
        mock_get_context.side_effect = Exception("Archivist connection failed")

        # Create the orchestrator
        orchestrator = EnhancedOrchestratorAgent(session_id="test-session")

        # Process a prompt that will cause an error in context retrieval
        result = await orchestrator.process_prompt("Hello, how are you?")

        # The result should indicate an error occurred but not crash the system
        self.assertIsInstance(result, str)
        self.assertIn(
            "error", result.lower()
        )  # Should contain some reference to an error


class TestPromptManagerIntegration(unittest.TestCase):
    """Integration tests for the PromptManager with real token counting"""

    def test_end_to_end_prompt_management(self):
        """Test the complete flow of prompt management with real token counting."""
        # Create a prompt manager with realistic settings
        config = PromptConfig(
            max_tokens=4096, reserved_tokens=500, strategy="intelligent"
        )
        prompt_manager = PromptManager(config)

        # Create a long prompt that would exceed the limit
        long_prompt = "Artificial intelligence is a wonderful field. " * 500
        context = "This is contextual information. " * 200

        # Process the prompt with context management
        result = prompt_manager.prepare_prompt(long_prompt, context)

        # Check that the result fits within limits
        stats = prompt_manager.get_context_usage_stats(result)
        self.assertLessEqual(stats["token_count"], 3596)  # 4096 - 500 reserved
        self.assertFalse(stats["over_limit"])

        # The result should still contain meaningful content
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_different_strategies(self):
        """Test different truncation strategies."""
        long_text = "Machine learning and AI are related fields. " * 1000

        strategies = ["truncate", "intelligent", "summarize"]

        for strategy in strategies:
            config = PromptConfig(
                max_tokens=1000, reserved_tokens=100, strategy=strategy
            )
            prompt_manager = PromptManager(config)

            result = prompt_manager.prepare_prompt(long_text)
            stats = prompt_manager.get_context_usage_stats(result)

            # All strategies should keep the result within the limit
            self.assertLessEqual(stats["token_count"], 900)  # 1000 - 100 reserved


if __name__ == "__main__":
    unittest.main()
