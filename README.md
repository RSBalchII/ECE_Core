# External Context Engine

The External Context Engine is an AI-powered system that processes and extracts information from various data sources, generating targeted queries for knowledge graph searches. It features multiple specialist agents that handle different types of processing tasks.

## Features

- **Multi-Agent Architecture**: Specialized agents for different processing tasks
- **Multi-Format Support**: Handles text files, PDFs, DOCX documents, and HTML content
- **Knowledge Graph Integration**: Generates optimized queries for knowledge graph searches
- **Flexible Configuration**: YAML-based configuration system
- **Comprehensive Testing**: Unit and integration tests for all components

## Specialist Agents

### ExtractorAgent
The ExtractorAgent is responsible for extracting specific information from unstructured data sources and generating targeted queries for the knowledge graph.

**Key Features:**
- Multi-format support (text, PDF, DOCX, HTML)
- Flexible extraction criteria (keywords, patterns, entities)
- Knowledge graph query generation
- Performance monitoring
- Comprehensive error handling

For detailed documentation, see [ExtractorAgent Documentation](docs/extractor_agent.md).

### DistillerAgent
The DistillerAgent is responsible for distilling raw text into structured, meaningful data. It identifies entities, relationships, and key points from the text and structures them for storage in the knowledge graph.

**Key Features:**
- Entity recognition (people, organizations, locations, etc.)
- Relationship extraction between identified entities
- Key point identification from text
- Data structuring for knowledge graph storage
- Performance optimization with caching
- Comprehensive error handling

For detailed documentation, see [DistillerAgent Documentation](docs/distiller_agent.md).

### WebSearchAgent
Performs web searches to gather external context.

### MultiModalIngestionAgent
Processes and ingests multi-modal content such as images, videos, and documents.

### CoherenceAgent
Ensures coherence and consistency in context and responses.

### SafetyAgent
Ensures the safety and appropriateness of content and responses.

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd External-Context-Engine
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The system is configured through `config.yaml`. Key configuration options include:

- Agent-specific settings
- Intent routing keywords
- Logging configuration

## Usage

Start the server:
```bash
python src/external_context_engine/main.py
```

The API will be available at `http://localhost:8000`.

### API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /chat` - Main chat endpoint

## Testing

Run unit tests:
```bash
pytest tests/
```

Run integration tests:
```bash
pytest tests/integration/
```

## Documentation

- [ExtractorAgent Documentation](docs/extractor_agent.md)
- [Specification](specs/extractor-agent/spec.md)
- [Implementation Plan](specs/extractor-agent/plan.md)
- [Task Breakdown](specs/extractor-agent/tasks.md)

## License

This project is licensed under the MIT License.
