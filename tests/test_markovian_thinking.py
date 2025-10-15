"""
Unit tests for the Markovian Thinking implementation.
"""

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ece.agents.common.trm_client import TRMClient, TRMConfig
from ece.agents.common.markovian_thinker import MarkovianThinker, MarkovianConfig


class TestTRMClient(unittest.IsolatedAsyncioTestCase):
    """Test cases for the TRMClient class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        config = TRMConfig(api_base="http://test:8081/v1", timeout=5.0)
        self.client = TRMClient(config)

    async def test_health_check(self):
        """Test the health check method."""
        with patch.object(self.client.client, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = await self.client.health_check()
            self.assertTrue(result)

    async def test_refine_thought(self):
        """Test the refine_thought method."""
        with patch.object(self.client.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"refined_thought": "This is a refined thought."}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            result = await self.client.refine_thought("test query", "original thought", "carryover")
            self.assertEqual(result, "This is a refined thought.")

    async def test_critique_thought(self):
        """Test the critique_thought method."""
        with patch.object(self.client.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "valid": True,
                "validity_score": 0.8,
                "issues": [],
                "suggestions": ["Good reasoning"]
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            result = await self.client.critique_thought("test query", "test thought")
            self.assertTrue(result["valid"])

    async def test_iterative_refinement(self):
        """Test the iterative_refinement method."""
        with patch.object(self.client, 'critique_thought') as mock_critique, \
             patch.object(self.client, 'refine_thought') as mock_refine:
            
            # Mock the critique to return valid results
            mock_critique.return_value = {
                "valid": True,
                "validity_score": 0.9,
                "issues": [],
                "suggestions": []
            }
            
            # Mock the refine to return increasingly refined thoughts
            mock_refine.side_effect = [
                "First refinement",
                "Second refinement", 
                "Final refined thought"
            ]
            
            result = await self.client.iterative_refinement("test query", "initial draft", max_iterations=3)
            self.assertEqual(result, "Final refined thought")


class TestMarkovianThinker(unittest.IsolatedAsyncioTestCase):
    """Test cases for the MarkovianThinker class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_trm_client = AsyncMock(spec=TRMClient)
        config = MarkovianConfig(max_iterations=2, stability_threshold=0.01)
        self.thinker = MarkovianThinker(self.mock_trm_client, config)

    async def test_markovian_reasoning_loop(self):
        """Test the full Markovian reasoning loop."""
        # Mock the internal methods
        self.thinker._get_initial_draft = AsyncMock(return_value="Initial draft")
        self.thinker._iterative_refinement = AsyncMock(return_value="Refined thought")
        self.thinker._get_final_answer = AsyncMock(return_value="Final answer")
        
        result = await self.thinker.markovian_reasoning_loop("test query", "initial context")
        
        self.assertEqual(result, "Final answer")
        self.thinker._get_initial_draft.assert_called_once_with("initial context\n\ntest query")
        self.thinker._iterative_refinement.assert_called_once_with("test query", "Initial draft")
        self.thinker._get_final_answer.assert_called_once_with("test query", "Refined thought")

    async def test_iterative_refinement(self):
        """Test the iterative refinement process."""
        # Set up the TRM client mock
        self.mock_trm_client.refine_thought = AsyncMock(side_effect=[
            "First refinement",
            "Second refinement"
        ])
        
        result = await self.thinker._iterative_refinement("test query", "initial draft")
        
        # Should have called refine_thought twice (as per max_iterations in config)
        self.assertEqual(self.mock_trm_client.refine_thought.call_count, 2)
        self.assertEqual(result, "Second refinement")

    async def test_markovian_chunked_reasoning(self):
        """Test the chunked reasoning functionality."""
        # Mock the TRM client to process chunks
        self.mock_trm_client.process_chunk = AsyncMock(return_value="processed chunk")
        self.thinker._iterative_refinement = AsyncMock(return_value="final refined result")
        
        long_text = "This is a very long text. " * 100  # Create a long text
        result = await self.thinker.markovian_chunked_reasoning("test query", long_text)
        
        # Should have processed multiple chunks
        self.assertGreater(self.mock_trm_client.process_chunk.call_count, 1)
        self.assertEqual(result, "final refined result")


class TestOrchestratorMarkovianIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for Markovian thinking in the orchestrator."""

    @patch('ece.agents.tier1.orchestrator.archivist_client.ArchivistClient')
    @patch('ece.components.context_cache.cache_manager.CacheManager')
    @patch('utcp_client.client.UTCPClient')
    def setUp(self, mock_utcp_client, mock_cache_manager, mock_archivist_client):
        """Set up test fixtures with mocks."""
        from ece.agents.tier1.orchestrator.orchestrator_agent import EnhancedOrchestratorAgent
        
        # Create a mock config
        self.mock_config = {
            'llm': {
                'active_provider': 'llama_cpp',
                'providers': {
                    'llama_cpp': {
                        'model_path': './models/test_model.gguf',
                        'api_base': 'http://localhost:8080/v1'
                    }
                }
            },
            'cache': {
                'redis_url': 'redis://localhost:6379'
            },
            'archivist': {
                'url': 'http://localhost:8003'
            },
            'OrchestraAgent': {
                'decision_tree': [
                    {'intent': 'ConversationalAgent', 'keywords': ['hello', 'hi', 'help']}
                ]
            },
            'ThinkerAgent': {
                'model': 'test-model',
                'personas': ['TestThinker'],
                'synthesis_model': 'test-synthesis-model'
            }
        }
        
        # Mock file operations
        with patch('builtins.open'):
            with patch('yaml.safe_load', return_value=self.mock_config):
                self.orchestrator = EnhancedOrchestratorAgent(session_id='test-session')
    
    async def test_should_use_markovian_thinking(self):
        """Test the logic for determining when to use Markovian thinking."""
        # Should use Markovian thinking for complex queries
        complex_prompts = [
            "Analyze the project requirements",
            "Evaluate the different approaches",
            "Develop a comprehensive strategy",
            "Investigate the root causes"
        ]
        
        for prompt in complex_prompts:
            result = await self.orchestrator._should_use_markovian_thinking(prompt)
            self.assertTrue(result, f"Should use Markovian thinking for: {prompt}")
        
        # Should NOT use Markovian thinking for simple queries
        simple_prompts = [
            "Hello",
            "What is the weather?",
            "Simple question"
        ]
        
        for prompt in simple_prompts:
            result = await self.orchestrator._should_use_markovian_thinking(prompt)
            self.assertFalse(result, f"Should not use Markovian thinking for: {prompt}")
    
    async def test_long_prompt_triggers_markovian_thinking(self):
        """Test that long prompts trigger Markovian thinking."""
        long_prompt = "This is a very long prompt. " * 50  # 50 repetitions
        result = await self.orchestrator._should_use_markovian_thinking(long_prompt)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()