# ExtractorAgent Documentation

## Overview

The ExtractorAgent is a specialist agent in the External Context Engine responsible for extracting specific information from unstructured data sources and generating targeted queries for the knowledge graph. It supports multiple data formats including text files, PDFs, DOCX documents, and HTML content.

## Features

- **Multi-format Support**: Extracts text from text files, PDFs, DOCX documents, and HTML content
- **Flexible Extraction Criteria**: Supports keyword-based extraction, pattern matching, and entity recognition
- **Knowledge Graph Integration**: Generates optimized queries for knowledge graph searches
- **Performance Monitoring**: Tracks processing time and memory usage
- **Error Handling**: Comprehensive error handling for file access and parsing issues

## API

### Data Models

#### ExtractionInput
```python
class ExtractionInput(BaseModel):
    data_source: str  # Path to the file or URL
    data_type: str    # Type of data (text, pdf, docx, html, etc.)
    criteria: Dict[str, Any]  # Extraction criteria or queries
```

#### ExtractionOutput
```python
class ExtractionOutput(BaseModel):
    extracted_data: List[Dict[str, Any]]  # List of extracted information
    queries: List[str]                    # List of generated queries
    metadata: Dict[str, Any]              # Metadata about the extraction process
```

### Methods

#### execute(data_source: str, data_type: str, criteria: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]

Execute the extraction process based on the provided data source and criteria.

**Parameters:**
- `data_source`: Path to the file or URL
- `data_type`: Type of data (text, pdf, docx, html, etc.)
- `criteria`: Extraction criteria or queries (optional)
- `**kwargs`: Additional parameters for extraction

**Returns:**
Dictionary containing extracted data, generated queries, and metadata

#### get_performance_metrics() -> Dict[str, Any]

Get the current performance metrics for the ExtractorAgent.

**Returns:**
Dictionary containing performance metrics

## Usage Examples

### Basic Text Extraction
```python
from src.external_context_engine.tools.extractor_agent import ExtractorAgent

agent = ExtractorAgent()

# Extract information from a text file
result = await agent.execute(
    data_source="/path/to/document.txt",
    data_type="text",
    criteria={}
)

print(f"Extracted {len(result['extracted_data'])} items")
print(f"Generated {len(result['queries'])} queries")
```

### Keyword-based Extraction
```python
# Extract sentences containing specific keywords
result = await agent.execute(
    data_source="/path/to/document.txt",
    data_type="text",
    criteria={
        "keywords": ["project", "deadline", "budget"]
    }
)
```

### Pattern-based Extraction
```python
# Extract information based on regex patterns
result = await agent.execute(
    data_source="/path/to/document.txt",
    data_type="text",
    criteria={
        "patterns": {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        }
    }
)
```

### Query Optimization
```python
# Generate optimized queries for knowledge graph searches
result = await agent.execute(
    data_source="/path/to/document.txt",
    data_type="text",
    criteria={
        "query_optimization": "aggressive"  # or "moderate"
    }
)
```

## Configuration

The ExtractorAgent can be configured through the `config.yaml` file:

```yaml
ExtractorAgent:
  enabled: true
  supported_types:
    - text
    - pdf
    - docx
    - html
  max_file_size: "50MB"
```

## Supported Data Types

- **text**: Plain text files (.txt)
- **pdf**: PDF documents (.pdf)
- **docx**: Microsoft Word documents (.docx)
- **html**: HTML documents (.html, .htm)

## Performance Metrics

The ExtractorAgent tracks the following performance metrics:
- Total extractions
- Successful extractions
- Failed extractions
- Total processing time
- Average processing time
- Memory usage

## Error Handling

The ExtractorAgent handles various error conditions:
- File not found errors
- Unsupported data types
- Parsing errors for different formats
- Network errors for URL-based sources
- Memory and processing time limits

All errors are logged and included in the metadata of the response.