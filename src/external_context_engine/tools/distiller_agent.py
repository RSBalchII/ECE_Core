"""
Distiller Agent for the External Context Engine

This agent is responsible for distilling raw text into structured, meaningful data
that can be efficiently stored in the knowledge graph. It identifies entities,
relationships, and key points from the text and structures them for storage.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import spacy
import logging
import re
from collections import defaultdict
import hashlib
import json

# Load the spaCy English model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If the model is not available, we'll use a basic approach
    nlp = None
    logging.warning("spaCy English model not found. Using basic text processing.")

logger = logging.getLogger(__name__)


class DistillationInput(BaseModel):
    """Input data model for the Distiller Agent"""
    text: str  # Raw text to be processed
    context: Dict[str, Any] = {}  # Optional context for the distillation process


class DistillationOutput(BaseModel):
    """Output data model for the Distiller Agent"""
    entities: List[Dict[str, Any]]  # List of identified entities
    relationships: List[Dict[str, Any]]  # List of relationships between entities
    key_points: List[str]  # List of key points extracted from the text
    metadata: Dict[str, Any]  # Metadata about the distillation process


class DistillerAgent:
    """
    Agent responsible for distilling raw text into structured, meaningful data.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the DistillerAgent.

        Args:
            config: Configuration dictionary for the agent
        """
        self.config = config or {}
        self.name = "DistillerAgent"
        self.description = "Distills raw text into structured, meaningful data"
        # Simple in-memory cache for demonstration purposes
        self._cache = {}
        # Maximum cache size
        self._max_cache_size = config.get('max_cache_size', 100) if config else 100
        
    async def execute(self, input_data: DistillationInput, **kwargs) -> DistillationOutput:
        """
        Execute the distillation process on the provided text.

        Args:
            input_data: The DistillationInput containing text to process
            **kwargs: Additional parameters for processing

        Returns:
            DistillationOutput containing structured data
        """
        logger.info(f"Executing distillation for text: {input_data.text[:50]}...")
        
        # Create a cache key from the input
        cache_key = self._create_cache_key(input_data)
        
        # Check if we have a cached result
        if cache_key in self._cache:
            logger.info("Returning cached result")
            cached_result = self._cache[cache_key]
            # Add cache hit information to metadata
            cached_result.metadata["cache_hit"] = True
            return cached_result
        
        try:
            # Record start time for performance monitoring
            import time
            start_time = time.time()
            
            # Process the text
            entities, relationships, key_points = self._process_text(input_data.text)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Create metadata
            metadata = {
                "agent": self.name,
                "text_length": len(input_data.text),
                "entities_count": len(entities),
                "relationships_count": len(relationships),
                "key_points_count": len(key_points),
                "processing_time_seconds": processing_time,
                "cache_hit": False
            }
            
            # Log performance metrics
            logger.info(f"Distillation completed in {processing_time:.4f} seconds")
            logger.info(f"Extracted {len(entities)} entities, {len(relationships)} relationships, {len(key_points)} key points")
            
            # Create the result
            result = DistillationOutput(
                entities=entities,
                relationships=relationships,
                key_points=key_points,
                metadata=metadata
            )
            
            # Cache the result
            self._cache_result(cache_key, result)
            
            return result
        except Exception as e:
            logger.error(f"Error during distillation process: {e}", exc_info=True)
            # Return empty results in case of error
            return DistillationOutput(
                entities=[],
                relationships=[],
                key_points=[],
                metadata={
                    "agent": self.name,
                    "error": str(e),
                    "cache_hit": False
                }
            )
    
    def _create_cache_key(self, input_data: DistillationInput) -> str:
        """
        Create a cache key from the input data.

        Args:
            input_data: The input data

        Returns:
            A string hash key
        """
        # Create a hash of the text and context
        hash_input = input_data.text + json.dumps(input_data.context, sort_keys=True)
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _cache_result(self, key: str, result: DistillationOutput):
        """
        Cache a result, managing cache size.

        Args:
            key: The cache key
            result: The result to cache
        """
        # If cache is at maximum size, remove the oldest entry
        if len(self._cache) >= self._max_cache_size:
            # Remove the first item (oldest)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        # Add the new result
        self._cache[key] = result
    
    def _process_text(self, text: str):
        """
        Process the text to extract entities, relationships, and key points.

        Args:
            text: The text to process

        Returns:
            Tuple of (entities, relationships, key_points)
        """
        # Extract entities
        entities = self._extract_entities(text)
        
        # Extract relationships
        relationships = self._extract_relationships(text)
        
        # Extract key points
        key_points = self._extract_key_points(text)
        
        return entities, relationships, key_points
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from the text using spaCy or basic pattern matching.

        Args:
            text: The text to process

        Returns:
            List of entities with their details
        """
        entities = []
        
        if nlp:
            # Use spaCy for entity recognition
            doc = nlp(text)
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "description": spacy.explain(ent.label_) if ent.label_ else None
                })
        else:
            # Basic entity extraction using regex patterns
            # Extract potential person names (capitalized words)
            person_pattern = r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b'
            persons = re.findall(person_pattern, text)
            for person in persons:
                if len(person.split()) > 1:  # Likely a full name
                    entities.append({
                        "text": person,
                        "label": "PERSON",
                        "description": "Person name"
                    })
            
            # Extract potential organizations (all caps or capitalized words)
            org_pattern = r'\b(?:[A-Z]{2,}|[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b'
            orgs = re.findall(org_pattern, text)
            for org in orgs:
                if len(org.split()) > 1 and org not in persons:  # Likely an organization
                    entities.append({
                        "text": org,
                        "label": "ORG",
                        "description": "Organization"
                    })
        
        return entities
    
    def _extract_relationships(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract relationships between entities from the text.

        Args:
            text: The text to process

        Returns:
            List of relationships with their details
        """
        relationships = []
        
        if nlp:
            # Use spaCy for relationship extraction
            doc = nlp(text)
            
            # Look for subject-verb-object patterns
            for token in doc:
                if token.dep_ == "nsubj" and token.head.pos_ == "VERB":
                    subject = token.text
                    verb = token.head.text
                    
                    # Find the object
                    for child in token.head.children:
                        if child.dep_ == "dobj":
                            obj = child.text
                            relationships.append({
                                "subject": subject,
                                "predicate": verb,
                                "object": obj,
                                "sentence": self._get_sentence(token.sent.text, subject, verb, obj)
                            })
        else:
            # Basic relationship extraction using simple patterns
            # Look for patterns like "X was founded by Y" or "X is part of Y"
            patterns = [
                (r'(\w+(?:\s\w+)*)\s+(was|is|were|are)\s+(founded|created|developed|part of|member of)\s+by\s+(\w+(?:\s\w+)*)', 
                 ["subject", "verb", "predicate", "object"]),
                (r'(\w+(?:\s\w+)*)\s+(is|was|are|were)\s+(part of|member of|located in|based in)\s+(\w+(?:\s\w+)*)', 
                 ["subject", "verb", "predicate", "object"])
            ]
            
            for pattern, group_names in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    if len(groups) == 4:
                        relationships.append({
                            "subject": groups[0],
                            "verb": groups[1],
                            "predicate": groups[2],
                            "object": groups[3],
                            "full_match": match.group(0)
                        })
        
        return relationships
    
    def _extract_key_points(self, text: str) -> List[str]:
        """
        Extract key points from the text.

        Args:
            text: The text to process

        Returns:
            List of key points
        """
        key_points = []
        
        # Split text into sentences
        sentences = re.split(r'[.!?]+', text)
        
        # Extract sentences that seem important (heuristic approach)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Sentences with numbers are often key points
            if re.search(r'\d+', sentence):
                key_points.append(sentence)
                continue
                
            # Sentences with certain keywords are often key points
            key_indicators = ["important", "key", "main", "primary", "significant", "notable", "crucial"]
            if any(indicator in sentence.lower() for indicator in key_indicators):
                key_points.append(sentence)
                continue
                
            # Sentences at the beginning or end might be key points
            # (This is a simplified approach)
        
        # If no key points found, return the first few sentences
        if not key_points:
            key_points = [s.strip() for s in sentences[:3] if s.strip()]
            
        return key_points
    
    def _get_sentence(self, sentence: str, *keywords) -> str:
        """
        Get a sentence containing specific keywords.

        Args:
            sentence: The sentence to process
            *keywords: Keywords to look for

        Returns:
            The sentence if it contains the keywords, otherwise an empty string
        """
        sentence_lower = sentence.lower()
        if all(keyword.lower() in sentence_lower for keyword in keywords if keyword):
            return sentence
        return ""