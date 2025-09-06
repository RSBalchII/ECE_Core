# QLearningGraphAgent Documentation

## Overview

The QLearningGraphAgent is a Reinforcement Learning-based graph navigation system that intelligently traverses the knowledge graph to find the most relevant information for complex queries. It uses Q-Learning to learn the most efficient paths between concepts in the graph, improving its navigation capabilities over time.

## Features

### Q-Learning Algorithm
- Implementation of the Q-Learning algorithm for graph navigation
- Epsilon-greedy strategy for balancing exploration and exploitation
- Q-value update mechanism based on path success

### Path Finding
- Directed search to specific target nodes
- Exploratory search in the neighborhood of a node
- Path ranking by Q-values

### Q-Table Management
- Sparse Q-Table implementation for memory efficiency
- Persistence support for maintaining learned knowledge across sessions

### Training
- Training with historical path data to improve navigation capabilities
- Metrics for tracking the convergence of the Q-Learning algorithm

## API Endpoints

### POST /q_learning/find_paths
Find optimal paths using Q-values for guidance.

**Request Body:**
```json
{
  "start_nodes": [{"name": "NodeA"}],
  "end_nodes": [{"name": "NodeB"}],
  "max_hops": 5
}
```

**Response:**
```json
[
  {
    "nodes": ["NodeA", "NodeC", "NodeB"],
    "relationships": [],
    "score": 0.8,
    "length": 2
  }
]
```

### POST /q_learning/update_q_values
Update Q-values based on the success of a path.

**Request Body:**
```json
{
  "path": ["NodeA", "NodeC", "NodeB"],
  "reward": 0.8
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Q-values updated"
}
```

### POST /q_learning/train
Train the Q-Learning agent with historical path data.

**Request Body:**
```json
{
  "training_data": [
    ["NodeA", "NodeB", 0.8],
    ["NodeB", "NodeC", 0.6]
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Training completed"
}
```

### GET /q_learning/convergence_metrics
Get metrics about Q-Learning convergence.

**Response:**
```json
{
  "converged": false,
  "episodes": 100,
  "average_reward": 0.75,
  "epsilon": 0.1,
  "q_table_size": 50
}
```

## Configuration

The QLearningGraphAgent can be configured in `config.yaml`:

```yaml
QLearningGraphAgent:
  enabled: true
  learning_rate: 0.1
  discount_factor: 0.9
  epsilon: 0.1
  max_episodes: 1000
  q_table_path: "./data/q_table.npy"
```

### Configuration Parameters

- `learning_rate`: Learning rate for Q-value updates (default: 0.1)
- `discount_factor`: Discount factor for future rewards (default: 0.9)
- `epsilon`: Exploration rate (default: 0.1)
- `max_episodes`: Maximum number of training episodes (default: 1000)
- `q_table_path`: Path to save/load Q-table (default: "./data/q_table.npy")

## Usage Examples

### Chat Interface
The QLearningGraphAgent can be accessed through the chat interface using the following keywords:
- "find path"
- "reason"
- "traverse graph"
- "navigate"
- "path finding"

### Direct API Usage
The agent can also be used directly through its API endpoints as shown in the API documentation above.

## Technical Implementation

### Core Components

1. **QLearningGraphAgent**: Main class implementing the Q-Learning algorithm for graph navigation
2. **QTable**: Q-Table implementation with persistence support
3. **MemoryPath**: Data model representing a path through the knowledge graph

### Integration with Neo4j
The agent integrates with the existing Neo4jManager for database operations, including:
- Getting neighboring nodes from the graph
- Finding shortest paths using Neo4j
- Executing Cypher queries

### Data Models

#### MemoryPath
```python
class MemoryPath(BaseModel):
    nodes: List[str] = Field(default_factory=list, description="Node names in the path")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Relationships in the path")
    score: float = Field(default=0.0, description="Path relevance score")
    length: int = Field(default=0, description="Path length (number of hops)")
```

## Testing

The QLearningGraphAgent includes comprehensive tests:
- Unit tests for all components
- Integration tests for API endpoints
- Import tests to verify module availability

To run the tests:
```bash
pytest tests/unit/q_learning/
pytest tests/integration/q_learning/
```

## Performance Considerations

- The Q-Table uses a sparse representation for memory efficiency
- Path finding algorithms are optimized for performance
- Caching mechanisms can be implemented for frequently accessed paths
- The agent supports persistence to maintain learned knowledge across sessions

## Future Enhancements

- Implement caching mechanisms for frequently accessed paths
- Optimize path finding algorithms for large graphs
- Add monitoring for performance metrics
- Create usage examples for the module
- Update the project's README with information about the Graph R1 module