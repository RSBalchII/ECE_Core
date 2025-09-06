# ExtractorAgent Usage Examples

This file provides comprehensive examples of how to use the ExtractorAgent in various scenarios.

## Basic Setup

```python
from src.external_context_engine.tools.extractor_agent import ExtractorAgent

# Initialize the agent
agent = ExtractorAgent()
```

## Example 1: Extract Information from a Text File

```python
import asyncio

async def extract_from_text_file():
    # Extract information from a text file
    result = await agent.execute(
        data_source="sample_documents/project_report.txt",
        data_type="text",
        criteria={}
    )
    
    print("Extraction Results:")
    print(f"- Extracted {len(result['extracted_data'])} items")
    print(f"- Generated {len(result['queries'])} queries")
    print(f"- Processing time: {result['metadata']['processing_time_seconds']} seconds")
    
    # Display extracted data
    for item in result['extracted_data']:
        print(f"Extracted Item: {item}")

# Run the example
asyncio.run(extract_from_text_file())
```

## Example 2: Keyword-based Extraction

```python
async def extract_with_keywords():
    # Extract sentences containing specific keywords
    result = await agent.execute(
        data_source="sample_documents/business_plan.docx",
        data_type="docx",
        criteria={
            "keywords": ["revenue", "profit", "growth", "market"]
        }
    )
    
    print("Keyword-based Extraction Results:")
    for item in result['extracted_data']:
        if 'matching_sentences' in item:
            print("Sentences containing keywords:")
            for sentence in item['matching_sentences'][:3]:  # Show first 3 sentences
                print(f"  - {sentence}")

# Run the example
asyncio.run(extract_with_keywords())
```

## Example 3: Pattern-based Extraction

```python
async def extract_with_patterns():
    # Extract information based on regex patterns
    result = await agent.execute(
        data_source="sample_documents/contact_list.pdf",
        data_type="pdf",
        criteria={
            "patterns": {
                "email_addresses": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                "phone_numbers": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
            }
        }
    )
    
    print("Pattern-based Extraction Results:")
    for item in result['extracted_data']:
        if 'pattern' in item:
            print(f"Pattern '{item['pattern']}' matches:")
            for match in item['matches'][:5]:  # Show first 5 matches
                print(f"  - {match}")

# Run the example
asyncio.run(extract_with_patterns())
```

## Example 4: Entity Recognition

```python
async def extract_entities():
    # Extract specific entity types
    result = await agent.execute(
        data_source="sample_documents/meeting_notes.html",
        data_type="html",
        criteria={
            "entities": "persons"  # Can also be "organizations"
        }
    )
    
    print("Entity Recognition Results:")
    for item in result['extracted_data']:
        if 'entity_type' in item and item['entity_type'] == 'persons':
            print("Identified persons:")
            for person in item['matches'][:5]:  # Show first 5 persons
                print(f"  - {person}")

# Run the example
asyncio.run(extract_entities())
```

## Example 5: Query Optimization

```python
async def extract_with_query_optimization():
    # Generate optimized queries for knowledge graph searches
    result = await agent.execute(
        data_source="sample_documents/research_paper.txt",
        data_type="text",
        criteria={
            "keywords": ["machine learning", "neural networks", "algorithm"],
            "query_optimization": "aggressive"  # Can also be "moderate"
        }
    )
    
    print("Query Optimization Results:")
    print(f"Generated {len(result['queries'])} optimized queries:")
    for query in result['queries'][:5]:  # Show first 5 queries
        print(f"  - {query}")

# Run the example
asyncio.run(extract_with_query_optimization())
```

## Example 6: Performance Monitoring

```python
async def monitor_performance():
    # Extract information and check performance metrics
    result = await agent.execute(
        data_source="sample_documents/large_document.pdf",
        data_type="pdf",
        criteria={
            "keywords": ["conclusion", "results", "findings"]
        }
    )
    
    print("Performance Monitoring Results:")
    print(f"Processing time: {result['metadata']['processing_time_seconds']} seconds")
    print(f"Memory used: {result['metadata']['memory_used_mb']} MB")
    
    # Get overall performance metrics
    metrics = agent.get_performance_metrics()
    print("\nOverall Performance Metrics:")
    print(f"Total extractions: {metrics['total_extractions']}")
    print(f"Successful extractions: {metrics['successful_extractions']}")
    print(f"Failed extractions: {metrics['failed_extractions']}")
    print(f"Average processing time: {metrics['average_processing_time']:.3f} seconds")

# Run the example
asyncio.run(monitor_performance())
```

## Example 7: Error Handling

```python
async def handle_errors():
    try:
        # Try to extract from a non-existent file
        result = await agent.execute(
            data_source="non_existent_file.txt",
            data_type="text",
            criteria={}
        )
        
        if not result['metadata']['extraction_success']:
            print(f"Extraction failed: {result['metadata']['error_message']}")
        else:
            print("Extraction successful")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Run the example
asyncio.run(handle_errors())
```

## Running the Examples

To run these examples:

1. Make sure you have the required dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Create sample documents in a `sample_documents` directory:
   ```bash
   mkdir -p sample_documents
   ```

3. Run a specific example:
   ```bash
   python examples/extractor_agent_examples.py
   ```

## Integration with the Main Application

The ExtractorAgent is also integrated with the main FastAPI application. You can use it through the `/chat` endpoint by including extraction-related keywords in your message:

```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "message": "Extract information from this document",
           "context": {
             "data_source": "path/to/document.pdf",
             "data_type": "pdf",
             "criteria": {
               "keywords": ["important", "deadline"]
             }
           }
         }'
```

This will automatically route to the ExtractorAgent based on the keywords in your message.