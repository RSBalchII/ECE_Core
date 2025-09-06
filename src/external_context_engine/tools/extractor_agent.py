"""
Extractor Agent for the External Context Engine

This agent is responsible for extracting specific information from unstructured data sources
and generating targeted queries for the knowledge graph.
"""
import os
import re
import logging
import time
import psutil
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel
import requests

# Import libraries for different data formats
import pdfplumber
from docx import Document
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Global variable to store performance metrics
_performance_metrics = {
    "total_extractions": 0,
    "successful_extractions": 0,
    "failed_extractions": 0,
    "total_processing_time": 0.0,
    "average_processing_time": 0.0
}


class ExtractionInput(BaseModel):
    """Input data model for the Extractor Agent"""
    data_source: str  # Path to the file or URL
    data_type: str    # Type of data (text, pdf, docx, html, etc.)
    criteria: Dict[str, Any]  # Extraction criteria or queries


class ExtractionOutput(BaseModel):
    """Output data model for the Extractor Agent"""
    extracted_data: List[Dict[str, Any]]  # List of extracted information
    queries: List[str]                    # List of generated queries
    metadata: Dict[str, Any]              # Metadata about the extraction process


class ExtractorAgent:
    """
    Agent responsible for extracting specific information from unstructured data sources
    and generating targeted queries for the knowledge graph.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ExtractorAgent.
        
        Args:
            config: Configuration dictionary for the agent
        """
        self.config = config or {}
        self.name = "ExtractorAgent"
        self.description = "Extracts specific information from unstructured data sources and generates targeted queries"
        self.supported_types = ["text", "pdf", "docx", "html"]
        
    async def execute(self, data_source: str, data_type: str, criteria: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute the extraction process based on the provided data source and criteria.
        
        Args:
            data_source: Path to the file or URL
            data_type: Type of data (text, pdf, docx, html, etc.)
            criteria: Extraction criteria or queries
            **kwargs: Additional parameters for extraction
            
        Returns:
            Dictionary containing extracted data, generated queries, and metadata
        """
        global _performance_metrics
        
        start_time = time.time()
        start_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # Memory in MB
        
        logger.info(f"Executing extraction for data source: {data_source} of type: {data_type}")
        
        # Increment total extractions counter
        _performance_metrics["total_extractions"] += 1
        
        # Validate input parameters
        if not data_source:
            raise ValueError("Data source cannot be empty")
            
        if data_type not in self.supported_types:
            raise ValueError(f"Unsupported data type: {data_type}. Supported types: {self.supported_types}")
            
        criteria = criteria or {}
        
        try:
            # Access the data source
            content = await self._access_data_source(data_source, data_type)
            
            # Extract text from the content
            text = self._extract_text(content, data_type)
            
            # Extract information based on criteria
            extracted_data = self._extract_information(text, criteria)
            
            # Generate queries for the knowledge graph
            queries = self._generate_queries(extracted_data, criteria)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            end_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # Memory in MB
            
            # Update performance metrics
            _performance_metrics["successful_extractions"] += 1
            _performance_metrics["total_processing_time"] += processing_time
            _performance_metrics["average_processing_time"] = (
                _performance_metrics["total_processing_time"] / _performance_metrics["successful_extractions"]
            )
            
            # Prepare metadata
            metadata = {
                "data_source": data_source,
                "data_type": data_type,
                "extraction_timestamp": self._get_current_timestamp(),
                "extraction_success": True,
                "extracted_items_count": len(extracted_data),
                "processing_time_seconds": round(processing_time, 3),
                "memory_used_mb": round(end_memory - start_memory, 2)
            }
            
            # Create the output model
            result = ExtractionOutput(
                extracted_data=extracted_data,
                queries=queries,
                metadata=metadata
            )
            
            logger.info(f"Extraction completed successfully in {processing_time:.3f} seconds, memory used: {end_memory - start_memory:.2f} MB")
            return result.dict()
            
        except Exception as e:
            logger.error(f"Error during extraction process: {str(e)}")
            
            # Update performance metrics for failed extractions
            _performance_metrics["failed_extractions"] += 1
            
            metadata = {
                "data_source": data_source,
                "data_type": data_type,
                "extraction_timestamp": self._get_current_timestamp(),
                "extraction_success": False,
                "error_message": str(e)
            }
            
            result = ExtractionOutput(
                extracted_data=[],
                queries=[],
                metadata=metadata
            )
            
            return result.dict()
    
    async def _access_data_source(self, data_source: str, data_type: str) -> Union[str, bytes]:
        """
        Access the data source based on whether it's a file path or URL.
        
        Args:
            data_source: Path to the file or URL
            data_type: Type of data
            
        Returns:
            Content of the data source
        """
        try:
            # Check if it's a URL
            if data_source.startswith("http://") or data_source.startswith("https://"):
                logger.info(f"Accessing data from URL: {data_source}")
                response = requests.get(data_source, timeout=30)
                response.raise_for_status()
                return response.content if data_type in ["pdf", "docx"] else response.text
            else:
                # Treat as file path
                logger.info(f"Accessing data from file: {data_source}")
                if not os.path.exists(data_source):
                    raise FileNotFoundError(f"File not found: {data_source}")
                    
                # For binary files, we need to read in binary mode
                mode = "rb" if data_type in ["pdf", "docx"] else "r"
                encoding = None if data_type in ["pdf", "docx"] else "utf-8"
                
                with open(data_source, mode, encoding=encoding) as file:
                    return file.read()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error accessing URL {data_source}: {str(e)}")
            raise
        except FileNotFoundError:
            logger.error(f"File not found: {data_source}")
            raise
        except Exception as e:
            logger.error(f"Error accessing data source {data_source}: {str(e)}")
            raise
    
    def _extract_text(self, content: Union[str, bytes], data_type: str) -> str:
        """
        Extract text from the content based on its type.
        
        Args:
            content: Content to extract text from
            data_type: Type of the content
            
        Returns:
            Extracted text
        """
        logger.info(f"Extracting text from {data_type} content")
        
        try:
            if data_type == "text":
                return content if isinstance(content, str) else content.decode("utf-8")
            elif data_type == "pdf":
                return self._extract_text_from_pdf(content)
            elif data_type == "docx":
                return self._extract_text_from_docx(content)
            elif data_type == "html":
                return self._extract_text_from_html(content)
            else:
                raise ValueError(f"Unsupported data type for text extraction: {data_type}")
        except Exception as e:
            logger.error(f"Error extracting text from {data_type}: {str(e)}")
            raise
    
    def _extract_text_from_pdf(self, content: bytes) -> str:
        """
        Extract text from PDF content.
        
        Args:
            content: PDF content as bytes
            
        Returns:
            Extracted text
        """
        text = ""
        try:
            # Create a temporary file to store the PDF content
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            # Extract text using pdfplumber
            with pdfplumber.open(temp_file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
            
        return text
    
    def _extract_text_from_docx(self, content: bytes) -> str:
        """
        Extract text from DOCX content.
        
        Args:
            content: DOCX content as bytes
            
        Returns:
            Extracted text
        """
        text = ""
        try:
            # Create a temporary file to store the DOCX content
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            # Extract text using python-docx
            doc = Document(temp_file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {str(e)}")
            raise
            
        return text
    
    def _extract_text_from_html(self, content: str) -> str:
        """
        Extract text from HTML content.
        
        Args:
            content: HTML content as string
            
        Returns:
            Extracted text
        """
        try:
            soup = BeautifulSoup(content, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            # Get text and clean it up
            text = soup.get_text()
            # Break into lines and remove leading and trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = ' '.join(chunk for chunk in chunks if chunk)
            return text
        except Exception as e:
            logger.error(f"Error extracting text from HTML: {str(e)}")
            raise
    
    def _extract_information(self, text: str, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract information from text based on criteria.
        
        Args:
            text: Text to extract information from
            criteria: Extraction criteria
            
        Returns:
            List of extracted information
        """
        logger.info("Extracting information based on criteria")
        extracted_data = []
        
        try:
            # If no criteria provided, extract basic information
            if not criteria:
                # Extract potential entities (words with capital letters)
                entities = re.findall(r'\b[A-Z][a-z]+\b', text)
                # Extract potential dates
                dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text)
                # Extract potential emails
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                # Extract potential phone numbers
                phones = re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text)
                
                extracted_data.append({
                    "entities": list(set(entities))[:10],  # Limit to first 10 unique entities
                    "dates": list(set(dates)),
                    "emails": list(set(emails)),
                    "phones": list(set(phones))
                })
            else:
                # Extract information based on specific criteria
                for key, value in criteria.items():
                    if key == "patterns":
                        # Extract based on regex patterns
                        for pattern_name, pattern in value.items():
                            matches = re.findall(pattern, text)
                            extracted_data.append({
                                "pattern": pattern_name,
                                "matches": list(set(matches))
                            })
                    elif key == "keywords":
                        # Extract sentences containing keywords
                        sentences = re.split(r'[.!?]+', text)
                        keyword_matches = []
                        for keyword in value:
                            for sentence in sentences:
                                if keyword.lower() in sentence.lower():
                                    keyword_matches.append(sentence.strip())
                        extracted_data.append({
                            "keywords": value,
                            "matching_sentences": list(set(keyword_matches))
                        })
                    elif key == "entities":
                        # Extract specific entity types
                        if value == "persons":
                            # Simple pattern for person names (first name + last name)
                            persons = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text)
                            extracted_data.append({
                                "entity_type": "persons",
                                "matches": list(set(persons))
                            })
                        elif value == "organizations":
                            # Simple pattern for organizations (all caps or title case phrases)
                            organizations = re.findall(r'\b[A-Z]{2,}(?: [A-Z]{2,})*\b|\b(?:[A-Z][a-z]+ ){1,3}Inc\.?\b|\b(?:[A-Z][a-z]+ ){1,3}Corp\.?\b|\b(?:[A-Z][a-z]+ ){1,3}Ltd\.?\b', text)
                            extracted_data.append({
                                "entity_type": "organizations",
                                "matches": list(set(organizations))
                            })
                        else:
                            # Generic entity extraction
                            entities = re.findall(r'\b[A-Z][a-z]+\b', text)
                            extracted_data.append({
                                "entity_type": value,
                                "matches": list(set(entities))
                            })
                    elif key == "structured_data":
                        # Extract structured data like key-value pairs
                        # Look for patterns like "Key: Value" or "Key - Value"
                        kv_pairs = re.findall(r'([A-Za-z\s]+)[:\-]\s*([^\n\r]+)', text)
                        structured_data = {key.strip(): value.strip() for key, value in kv_pairs}
                        extracted_data.append({
                            "structured_data": structured_data
                        })
                    else:
                        # Generic extraction for other criteria
                        extracted_data.append({
                            key: value
                        })
                        
        except Exception as e:
            logger.error(f"Error extracting information: {str(e)}")
            raise
            
        return extracted_data
    
    def _generate_queries(self, extracted_data: List[Dict[str, Any]], criteria: Dict[str, Any]) -> List[str]:
        """
        Generate knowledge graph queries based on extracted data.
        
        Args:
            extracted_data: Data extracted from the source
            criteria: Extraction criteria
            
        Returns:
            List of generated queries
        """
        logger.info("Generating knowledge graph queries")
        queries = []
        
        try:
            # Generate queries based on extracted data
            for item in extracted_data:
                if "entities" in item:
                    # Create entity-based queries
                    for entity in item["entities"][:5]:  # Limit to first 5 entities
                        queries.append(f"MATCH (e:Entity {{name: '{entity}'}}) RETURN e LIMIT 10")
                        queries.append(f"MATCH (e:Entity {{name: '{entity}'}})-[r]-(related) RETURN e, r, related LIMIT 20")
                if "emails" in item:
                    # Create email-based queries
                    for email in item["emails"][:3]:  # Limit to first 3 emails
                        queries.append(f"MATCH (p:Person {{email: '{email}'}}) RETURN p LIMIT 10")
                if "dates" in item:
                    # Create date-based queries
                    for date in item["dates"][:3]:  # Limit to first 3 dates
                        queries.append(f"MATCH (e:Event {{date: '{date}'}}) RETURN e LIMIT 10")
                if "keywords" in item:
                    # Create keyword-based queries
                    for sentence in item["matching_sentences"][:3]:  # Limit to first 3 sentences
                        # Extract potential entities from sentences
                        entities = re.findall(r'\b[A-Z][a-z]+\b', sentence)
                        for entity in entities[:2]:  # Limit to first 2 entities per sentence
                            queries.append(f"MATCH (e:Entity {{name: '{entity}'}}) RETURN e LIMIT 10")
                if "persons" in item:
                    # Create person-based queries
                    for person in item["matches"][:3]:  # Limit to first 3 persons
                        queries.append(f"MATCH (p:Person {{name: '{person}'}}) RETURN p LIMIT 10")
                        # Also create queries to find relationships of this person
                        queries.append(f"MATCH (p:Person {{name: '{person}'}})-[r]-(related) RETURN p, r, related LIMIT 20")
                if "organizations" in item:
                    # Create organization-based queries
                    for org in item["matches"][:3]:  # Limit to first 3 organizations
                        queries.append(f"MATCH (o:Organization {{name: '{org}'}}) RETURN o LIMIT 10")
                        # Also create queries to find relationships of this organization
                        queries.append(f"MATCH (o:Organization {{name: '{org}'}})-[r]-(related) RETURN o, r, related LIMIT 20")
                if "structured_data" in item:
                    # Create queries based on structured data
                    for key, value in item["structured_data"].items():
                        queries.append(f"MATCH (n) WHERE n.{key} = '{value}' RETURN n LIMIT 10")
            
            # Apply query optimization based on criteria
            if criteria and "query_optimization" in criteria:
                optimization_level = criteria["query_optimization"]
                if optimization_level == "aggressive":
                    # Reduce the number of queries by combining similar ones
                    queries = self._optimize_queries_aggressive(queries)
                elif optimization_level == "moderate":
                    # Apply moderate optimization
                    queries = self._optimize_queries_moderate(queries)
                            
        except Exception as e:
            logger.error(f"Error generating queries: {str(e)}")
            raise
            
        # Remove duplicate queries
        unique_queries = list(set(queries))
        logger.info(f"Generated {len(unique_queries)} unique queries")
        return unique_queries
    
    def _optimize_queries_aggressive(self, queries: List[str]) -> List[str]:
        """
        Aggressively optimize queries by combining similar ones.
        
        Args:
            queries: List of queries to optimize
            
        Returns:
            Optimized list of queries
        """
        logger.info("Applying aggressive query optimization")
        optimized_queries = []
        
        # Group similar queries
        entity_queries = [q for q in queries if "Entity" in q and "RETURN e" in q]
        person_queries = [q for q in queries if "Person" in q and "RETURN p" in q]
        org_queries = [q for q in queries if "Organization" in q and "RETURN o" in q]
        relationship_queries = [q for q in queries if "-[r]-(related)" in q]
        other_queries = [q for q in queries if q not in entity_queries + person_queries + org_queries + relationship_queries]
        
        # Combine entity queries
        if entity_queries:
            optimized_queries.append("MATCH (e:Entity) WHERE e.name IN [{entities}] RETURN e LIMIT 50".format(
                entities=", ".join([q.split("'")[1] for q in entity_queries[:10] if "'" in q])
            ))
        
        # Combine person queries
        if person_queries:
            optimized_queries.append("MATCH (p:Person) WHERE p.name IN [{persons}] RETURN p LIMIT 30".format(
                persons=", ".join([q.split("'")[1] for q in person_queries[:5] if "'" in q])
            ))
        
        # Combine organization queries
        if org_queries:
            optimized_queries.append("MATCH (o:Organization) WHERE o.name IN [{orgs}] RETURN o LIMIT 30".format(
                orgs=", ".join([q.split("'")[1] for q in org_queries[:5] if "'" in q])
            ))
        
        # Add a few relationship queries
        optimized_queries.extend(relationship_queries[:3])
        
        # Add other queries
        optimized_queries.extend(other_queries[:5])
        
        return optimized_queries
    
    def _optimize_queries_moderate(self, queries: List[str]) -> List[str]:
        """
        Apply moderate query optimization.
        
        Args:
            queries: List of queries to optimize
            
        Returns:
            Optimized list of queries
        """
        logger.info("Applying moderate query optimization")
        # For moderate optimization, we'll just limit the number of queries
        # and ensure we have a good mix of entity, relationship, and other queries
        entity_queries = [q for q in queries if "Entity" in q]
        relationship_queries = [q for q in queries if "-[r]-(related)" in q]
        other_queries = [q for q in queries if q not in entity_queries + relationship_queries]
        
        # Take a balanced sample
        optimized_queries = (
            entity_queries[:5] + 
            relationship_queries[:3] + 
            other_queries[:5]
        )
        
        return optimized_queries
    
    def _get_current_timestamp(self) -> str:
        """
        Get the current timestamp.
        
        Returns:
            Current timestamp as string
        """
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get the current performance metrics for the ExtractorAgent.
        
        Returns:
            Dictionary containing performance metrics
        """
        global _performance_metrics
        return _performance_metrics.copy()