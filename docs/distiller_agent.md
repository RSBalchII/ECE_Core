# DistillerAgent Documentation

## Overview

The DistillerAgent is a specialist agent in the External Context Engine responsible for distilling raw text into structured, meaningful data. It identifies entities, relationships, and key points from the text and structures them for storage in the knowledge graph.

## Functionality

The DistillerAgent provides the following core functionality:

1. **Entity Recognition**: Identifies named entities in the text (people, organizations, locations, etc.)
2. **Relationship Extraction**: Determines relationships between identified entities
3. **Key Point Identification**: Extracts important points and facts from the text
4. **Data Structuring**: Converts identified information into structured data formats

## API Endpoints

### POST /distill

Distills raw text into structured data.

**Request Body**:
```json
{
  "text": "string",           // Raw text to be processed
  "context": {}              // Optional context for the distillation process
}
```

**Response**:
```json
{
  "entities": [              // List of identified entities
    {
      "text": "string",     // The entity text
      "label": "string",    // The entity type (e.g., PERSON, ORG)
      "start": 0,           // Start position in the text (if using spaCy)
      "end": 0,             // End position in the text (if using spaCy)
      "description": "string" // Description of the entity type
    }
  ],
  "relationships": [         // List of relationships between entities
    {
      "subject": "string",   // The subject of the relationship
      "predicate": "string", // The predicate/verb of the relationship
      "object": "string",    // The object of the relationship
      "sentence": "string"   // The sentence containing the relationship
    }
  ],
  "key_points": [           // List of key points extracted from the text
    "string"
  ],
  "metadata": {             // Metadata about the distillation process
    "agent": "string",      // The agent name
    "text_length": 0,       // Length of the input text
    "entities_count": 0,    // Number of entities found
    "relationships_count": 0, // Number of relationships found
    "key_points_count": 0,  // Number of key points found
    "processing_time_seconds": 0.0, // Processing time (if not cached)
    "cache_hit": true       // Whether the result was cached
  }
}
```

### POST /chat

The DistillerAgent can also be accessed through the main chat endpoint when the message contains keywords related to distillation (distill, extract, entities, relationships, structure, summarize).

**Request Body**:
```json
{
  "message": "string",       // Chat message (should contain distillation keywords)
  "context": {}             // Optional context
}
```

**Response**:
```json
{
  "response": "string",      // Summary of distillation results
  "context": {},            // Updated context
  "agent_used": "DistillerAgent" // The agent that processed the request
}
```

## Usage Examples

### Example 1: Basic Distillation

**Request**:
```bash
curl -X POST "http://localhost:8000/distill" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Google was founded by Larry Page and Sergey Brin while they were Ph.D. students at Stanford University.",
    "context": {}
  }'
```

**Response**:
```json
{
  "entities": [
    {
      "text": "Google",
      "label": "ORG",
      "start": 0,
      "end": 6,
      "description": "Companies, agencies, institutions, etc."
    },
    {
      "text": "Larry Page",
      "label": "PERSON",
      "start": 22,
      "end": 32,
      "description": "People, including fictional"
    },
    {
      "text": "Sergey Brin",
      "label": "PERSON",
      "start": 37,
      "end": 48,
      "description": "People, including fictional"
    }
  ],
  "relationships": [],
  "key_points": [
    "Google was founded by Larry Page and Sergey Brin while they were Ph",
    "D",
    "students at Stanford University"
  ],
  "metadata": {
    "agent": "DistillerAgent",
    "text_length": 103,
    "entities_count": 3,
    "relationships_count": 0,
    "key_points_count": 3,
    "processing_time_seconds": 0.023,
    "cache_hit": false
  }
}
```

### Example 2: Using Chat Endpoint

**Request**:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Distill this text: Google was founded by Larry Page and Sergey Brin.",
    "context": {}
  }'
```

**Response**:
```json
{
  "response": "Distilled 3 entities, 0 relationships, and 1 key points from the text.",
  "context": {},
  "agent_used": "DistillerAgent"
}
```

### Example 3: Processing Research Paper Abstract

**Request**:
```bash
curl -X POST "http://localhost:8000/distill" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This paper presents a novel approach to natural language processing using transformer architectures. The method achieves state-of-the-art results on several benchmark datasets including GLUE and SuperGLUE. Our model, called DistilBERT, is 60% smaller and 60% faster than BERT while retaining 97% of its language understanding capabilities.",
    "context": {"domain": "nlp"}
  }'
```

**Response**:
```json
{
  "entities": [
    {
      "text": "natural language processing",
      "label": "WORK_OF_ART",
      "description": "Titles of books, songs, etc."
    },
    {
      "text": "transformer architectures",
      "label": "WORK_OF_ART",
      "description": "Titles of books, songs, etc."
    },
    {
      "text": "GLUE",
      "label": "WORK_OF_ART",
      "description": "Titles of books, songs, etc."
    },
    {
      "text": "SuperGLUE",
      "label": "WORK_OF_ART",
      "description": "Titles of books, songs, etc."
    },
    {
      "text": "DistilBERT",
      "label": "WORK_OF_ART",
      "description": "Titles of books, songs, etc."
    },
    {
      "text": "BERT",
      "label": "WORK_OF_ART",
      "description": "Titles of books, songs, etc."
    }
  ],
  "relationships": [
    {
      "subject": "method",
      "predicate": "achieves",
      "object": "state-of-the-art results"
    },
    {
      "subject": "DistilBERT",
      "predicate": "is",
      "object": "60% smaller and 60% faster than BERT"
    },
    {
      "subject": "DistilBERT",
      "predicate": "retaining",
      "object": "97% of its language understanding capabilities"
    }
  ],
  "key_points": [
    "This paper presents a novel approach to natural language processing using transformer architectures",
    "The method achieves state-of-the-art results on several benchmark datasets including GLUE and SuperGLUE",
    "Our model, called DistilBERT, is 60% smaller and 60% faster than BERT while retaining 97% of its language understanding capabilities"
  ],
  "metadata": {
    "agent": "DistillerAgent",
    "text_length": 342,
    "entities_count": 6,
    "relationships_count": 3,
    "key_points_count": 3,
    "processing_time_seconds": 0.045,
    "cache_hit": false
  }
}
```

### Example 4: News Article Processing

**Request**:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Extract key information from this: Apple Inc. announced quarterly earnings of $1.20 per share, exceeding analyst expectations of $1.15. The company reported revenue of $89.5 billion for the quarter ending in March 2023.",
    "context": {"type": "financial_news"}
  }'
```

**Response**:
```json
{
  "response": "Distilled 4 entities, 2 relationships, and 2 key points from the text.",
  "context": {
    "type": "financial_news"
  },
  "agent_used": "DistillerAgent"
}
```

## Configuration

The DistillerAgent can be configured in the `config.yaml` file:

```yaml
agents:
  DistillerAgent:
    enabled: true
    max_cache_size: 100  # Maximum number of cached results
```

## Performance Optimization

The DistillerAgent includes several performance optimizations:

1. **Caching**: Results are cached to avoid reprocessing the same text
2. **spaCy Integration**: Uses spaCy for efficient NLP processing when available
3. **Asynchronous Processing**: Supports async/await for non-blocking operations

## Error Handling

The DistillerAgent includes comprehensive error handling:

1. **Input Validation**: Validates input data models
2. **Exception Handling**: Gracefully handles processing errors
3. **Fallback Mechanisms**: Provides basic text processing when spaCy is not available

## Best Practices

1. **Text Length**: For optimal performance, keep text length reasonable (under 10,000 characters)
2. **Context Usage**: Provide relevant context to improve distillation accuracy
3. **Caching**: Take advantage of caching for repeated processing of the same text
4. **Error Handling**: Always check the metadata for error information in production code