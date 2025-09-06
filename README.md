# External Context Engine

The External Context Engine is an AI-powered system that processes and extracts information from various data sources, generating targeted queries for knowledge graph searches. It features multiple specialist agents that handle different types of processing tasks.

## Features

- **Multi-Agent Architecture**: Specialized agents for different processing tasks
- **Multi-Format Support**: Handles text files, PDFs, DOCX documents, and HTML content
- **Knowledge Graph Integration**: Generates optimized queries for knowledge graph searches
- **Flexible Configuration**: YAML-based configuration system
- **Comprehensive Testing**: Unit and integration tests for all components

## Specialist Agents

### ArchivistAgent
The ArchivistAgent is responsible for managing the knowledge graph by storing and retrieving structured information using Neo4j as the persistence layer.

**Key Features:**
- Store entities and relationships in the knowledge graph
- Retrieve information using Cypher queries
- Update existing entities and relationships
- Delete entities and relationships
- Integration with the main application through chat interface or direct API endpoints

For detailed documentation, see [ArchivistAgent Documentation](docs/archivist_agent.md).

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

### QLearningGraphAgent
The QLearningGraphAgent is a Reinforcement Learning-based graph navigation system that intelligently traverses the knowledge graph to find the most relevant information for complex queries.

**Key Features:**
- Q-Learning algorithm for graph navigation
- Path finding with Q-value guidance
- Q-Table persistence for maintaining learned knowledge
- Training with historical path data
- Epsilon-greedy strategy for balancing exploration and exploitation
- API endpoints for integration with the main application

For detailed documentation, see [QLearningGraphAgent Documentation](docs/q_learning_agent.md).

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
- `POST /archive/store` - Store data in the knowledge graph
- `POST /archive/retrieve` - Retrieve data from the knowledge graph
- `POST /archive/update` - Update data in the knowledge graph
- `POST /archive/delete` - Delete data from the knowledge graph
- `POST /q_learning/find_paths` - Find optimal paths using Q-values
- `POST /q_learning/update_q_values` - Update Q-values based on path success
- `POST /q_learning/train` - Train the agent with historical data
- `GET /q_learning/convergence_metrics` - Get convergence metrics

## Enhancement Opportunities

The QLearningGraphAgent has been analyzed for enhancement opportunities using Neo4j's advanced features. For detailed information about these opportunities, see the [QLearning Enhancement Documentation](docs/README.md).

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

- [ArchivistAgent Documentation](docs/archivist_agent.md)
- [ExtractorAgent Documentation](docs/extractor_agent.md)
- [DistillerAgent Documentation](docs/distiller_agent.md)
- [QLearningGraphAgent Documentation](docs/q_learning_agent.md)
- [QLearning Enhancement Documentation](docs/README.md)
- [Specification](specs/extractor-agent/spec.md)
- [Implementation Plan](specs/extractor-agent/plan.md)
- [Task Breakdown](specs/extractor-agent/tasks.md)

## License

This project is licensed under the MIT License.
