"""
Unit tests for the DistillerAgent
"""

import sys
import os
import pytest
from typing import Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.external_context_engine.tools.distiller_agent import (
    DistillerAgent, 
    DistillationInput, 
    DistillationOutput
)

class TestDistillerAgent:
    """Test suite for the DistillerAgent"""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.agent = DistillerAgent()
        self.sample_text = "Google was founded by Larry Page and Sergey Brin while they were Ph.D. students at Stanford University."
    
    def test_agent_initialization(self):
        """Test that the DistillerAgent initializes correctly"""
        assert self.agent.name == "DistillerAgent"
        assert self.agent.description == "Distills raw text into structured, meaningful data"
        assert hasattr(self.agent, '_cache')
        assert hasattr(self.agent, '_max_cache_size')
    
    def test_distillation_input_model(self):
        """Test the DistillationInput model"""
        input_data = DistillationInput(text=self.sample_text, context={"source": "test"})
        assert input_data.text == self.sample_text
        assert input_data.context == {"source": "test"}
    
    def test_distillation_output_model(self):
        """Test the DistillationOutput model"""
        entities = [{"text": "Google", "label": "ORG"}]
        relationships = [{"subject": "Google", "predicate": "founded by", "object": "Larry Page"}]
        key_points = ["Google was founded by Larry Page and Sergey Brin"]
        metadata = {"agent": "DistillerAgent", "text_length": 100}
        
        output_data = DistillationOutput(
            entities=entities,
            relationships=relationships,
            key_points=key_points,
            metadata=metadata
        )
        
        assert output_data.entities == entities
        assert output_data.relationships == relationships
        assert output_data.key_points == key_points
        assert output_data.metadata == metadata
    
    def test_execute_method(self):
        """Test the execute method of the DistillerAgent"""
        input_data = DistillationInput(text=self.sample_text, context={})
        import asyncio
        result = asyncio.run(self.agent.execute(input_data))
        
        # Check that result is of correct type
        assert isinstance(result, DistillationOutput)
        
        # Check that result has required fields
        assert hasattr(result, 'entities')
        assert hasattr(result, 'relationships')
        assert hasattr(result, 'key_points')
        assert hasattr(result, 'metadata')
        
        # Check that metadata contains required fields
        assert 'agent' in result.metadata
        assert 'text_length' in result.metadata
        assert 'entities_count' in result.metadata
        assert 'relationships_count' in result.metadata
        assert 'key_points_count' in result.metadata
        assert 'processing_time_seconds' in result.metadata
        assert 'cache_hit' in result.metadata
    
    def test_entity_extraction(self):
        """Test entity extraction functionality"""
        input_data = DistillationInput(text=self.sample_text, context={})
        import asyncio
        result = asyncio.run(self.agent.execute(input_data))
        
        # Check that entities were extracted
        assert len(result.entities) > 0
        
        # Check that entities have required fields
        for entity in result.entities:
            assert 'text' in entity
            assert 'label' in entity
    
    def test_relationship_extraction(self):
        """Test relationship extraction functionality"""
        input_data = DistillationInput(text=self.sample_text, context={})
        import asyncio
        result = asyncio.run(self.agent.execute(input_data))
        
        # Check that relationships have required fields (if any were found)
        for relationship in result.relationships:
            assert 'subject' in relationship
            assert 'predicate' in relationship or 'verb' in relationship
            assert 'object' in relationship
    
    def test_key_point_extraction(self):
        """Test key point extraction functionality"""
        text = "This is an important finding. The key result shows that the method is effective. It has 5 advantages."
        input_data = DistillationInput(text=text, context={})
        import asyncio
        result = asyncio.run(self.agent.execute(input_data))
        
        # Check that key points were extracted
        assert len(result.key_points) > 0
    
    def test_caching_functionality(self):
        """Test that caching works correctly"""
        input_data = DistillationInput(text=self.sample_text, context={})
        
        # First execution
        import asyncio
        result1 = asyncio.run(self.agent.execute(input_data))
        assert result1.metadata['cache_hit'] == False
        
        # Second execution (should use cache)
        result2 = asyncio.run(self.agent.execute(input_data))
        assert result2.metadata['cache_hit'] == True
        
        # Results should be identical
        assert result1.entities == result2.entities
        assert result1.relationships == result2.relationships
        assert result1.key_points == result2.key_points
    
    def test_error_handling(self):
        """Test error handling with invalid input"""
        # Test with empty text
        input_data = DistillationInput(text="", context={})
        import asyncio
        result = asyncio.run(self.agent.execute(input_data))
        
        # Should still return a valid DistillationOutput
        assert isinstance(result, DistillationOutput)
        assert 'error' in result.metadata or len(result.entities) == 0
    
    def test_large_text_handling(self):
        """Test handling of large text inputs"""
        # Create a large text sample
        large_text = "This is a sample sentence. " * 1000
        input_data = DistillationInput(text=large_text, context={})
        import asyncio
        result = asyncio.run(self.agent.execute(input_data))
        
        # Should still return a valid DistillationOutput
        assert isinstance(result, DistillationOutput)
        assert result.metadata['text_length'] == len(large_text)

if __name__ == "__main__":
    pytest.main([__file__])