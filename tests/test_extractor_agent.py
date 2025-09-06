"""
Unit tests for the ExtractorAgent.
"""
import pytest
import os
import tempfile
from src.external_context_engine.tools.extractor_agent import ExtractorAgent, ExtractionInput, ExtractionOutput


class TestExtractorAgent:
    """Test suite for ExtractorAgent unit tests"""
    
    def setup_method(self):
        """Setup method to initialize the ExtractorAgent before each test"""
        self.agent = ExtractorAgent()
    
    def test_initialization(self):
        """Test that the ExtractorAgent initializes correctly"""
        assert self.agent.name == "ExtractorAgent"
        assert self.agent.description == "Extracts specific information from unstructured data sources and generates targeted queries"
        assert self.agent.supported_types == ["text", "pdf", "docx", "html"]
    
    def test_data_models(self):
        """Test the ExtractionInput and ExtractionOutput data models"""
        # Test ExtractionInput
        input_data = ExtractionInput(
            data_source="test.txt",
            data_type="text",
            criteria={"keywords": ["test"]}
        )
        assert input_data.data_source == "test.txt"
        assert input_data.data_type == "text"
        assert input_data.criteria == {"keywords": ["test"]}
        
        # Test ExtractionOutput
        output_data = ExtractionOutput(
            extracted_data=[{"test": "data"}],
            queries=["MATCH (n) RETURN n"],
            metadata={"test": "metadata"}
        )
        assert output_data.extracted_data == [{"test": "data"}]
        assert output_data.queries == ["MATCH (n) RETURN n"]
        assert output_data.metadata == {"test": "metadata"}
    
    def test_extract_text_from_text_file(self):
        """Test extracting text from a text file"""
        # Create a temporary text file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as temp_file:
            temp_file.write("This is a test text file.\\nIt has multiple lines.\\nAnd some content to extract.")
            temp_file_path = temp_file.name
        
        try:
            # Test the _extract_text method
            with open(temp_file_path, "r") as file:
                content = file.read()
            
            extracted_text = self.agent._extract_text(content, "text")
            assert "This is a test text file." in extracted_text
            assert "It has multiple lines." in extracted_text
            assert "And some content to extract." in extracted_text
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_extract_information_without_criteria(self):
        """Test extracting information without specific criteria"""
        text = "John Doe can be reached at john.doe@example.com. The meeting is on 12/25/2023."
        
        extracted_data = self.agent._extract_information(text, {})
        
        assert len(extracted_data) == 1
        assert "entities" in extracted_data[0]
        assert "dates" in extracted_data[0]
        assert "emails" in extracted_data[0]
        
        # Check that email was extracted
        assert "john.doe@example.com" in extracted_data[0]["emails"]
        
        # Check that date was extracted
        assert "12/25/2023" in extracted_data[0]["dates"]
    
    def test_extract_information_with_keywords_criteria(self):
        """Test extracting information with keywords criteria"""
        text = "The project deadline is approaching. We need to complete the project by Friday."
        
        criteria = {"keywords": ["project", "deadline"]}
        extracted_data = self.agent._extract_information(text, criteria)
        
        assert len(extracted_data) == 1
        assert "keywords" in extracted_data[0]
        assert "matching_sentences" in extracted_data[0]
        
        # Check that the keywords are in the result
        assert "project" in extracted_data[0]["keywords"]
        assert "deadline" in extracted_data[0]["keywords"]
        
        # Check that matching sentences were found
        assert len(extracted_data[0]["matching_sentences"]) > 0
    
    def test_generate_queries(self):
        """Test generating queries from extracted data"""
        extracted_data = [
            {
                "entities": ["John Doe", "Acme Corp"],
                "emails": ["john.doe@example.com"],
                "dates": ["12/25/2023"]
            }
        ]
        
        queries = self.agent._generate_queries(extracted_data, {})
        
        # Check that queries were generated
        assert len(queries) > 0
        
        # Check for entity-based queries
        entity_queries = [q for q in queries if "Entity" in q]
        assert len(entity_queries) > 0
        
        # Check for email-based queries
        email_queries = [q for q in queries if "email" in q]
        assert len(email_queries) > 0
        
        # Check for date-based queries
        date_queries = [q for q in queries if "date" in q]
        assert len(date_queries) > 0
    
    def test_generate_optimized_queries(self):
        """Test generating optimized queries"""
        extracted_data = [
            {
                "entities": ["John Doe", "Jane Smith", "Acme Corp"],
            }
        ]
        
        # Test aggressive optimization
        criteria = {"query_optimization": "aggressive"}
        queries = self.agent._generate_queries(extracted_data, criteria)
        
        assert len(queries) > 0
        
        # Test moderate optimization
        criteria = {"query_optimization": "moderate"}
        queries = self.agent._generate_queries(extracted_data, criteria)
        
        assert len(queries) > 0
    
    def test_performance_metrics(self):
        """Test performance metrics tracking"""
        # Get initial metrics
        initial_metrics = self.agent.get_performance_metrics()
        
        # Check that metrics have expected keys
        assert "total_extractions" in initial_metrics
        assert "successful_extractions" in initial_metrics
        assert "failed_extractions" in initial_metrics
        assert "total_processing_time" in initial_metrics
        assert "average_processing_time" in initial_metrics


if __name__ == "__main__":
    pytest.main([__file__])