# ArchivistAgent Documentation

## Overview

The ArchivistAgent is responsible for managing the knowledge graph by storing and retrieving structured information using Neo4j as the persistence layer.

## Features

- Store entities and relationships in the knowledge graph
- Retrieve information using Cypher queries
- Update existing entities and relationships
- Delete entities and relationships
- Integration with the main application through chat interface or direct API endpoints

## API Endpoints

### Store Data
- **Endpoint**: `/archive/store`
- **Method**: POST
- **Request Body**: 
  ```json
  {
    "data": [
      // Array of Entity or Relationship objects
    ]
  }
  ```
- **Response**: Confirmation of storage operation

### Retrieve Data
- **Endpoint**: `/archive/retrieve`
- **Method**: POST
- **Request Body**: 
  ```json
  {
    "query": {
      "cypher": "MATCH (n) RETURN n",
      "parameters": {}
    }
  }
  ```
- **Response**: Query results

### Update Data
- **Endpoint**: `/archive/update`
- **Method**: POST
- **Request Body**: 
  ```json
  {
    "item": {
      // Entity or Relationship object
    }
  }
  ```
- **Response**: Confirmation of update operation

### Delete Data
- **Endpoint**: `/archive/delete`
- **Method**: POST
- **Request Body**: 
  ```json
  {
    "id": "entity_or_relationship_id",
    "type": "entity|relationship"
  }
  ```
- **Response**: Confirmation of deletion operation

## Chat Interface

The ArchivistAgent can also be accessed through the main chat interface by using keywords like "archive", "store", "memory", "persist", or "save" in your message.

Example:
```
User: "archive information about John Doe who works at ACME Corp"
Context: {
  "structured_data": [
    {
      "id": "1",
      "type": "Person",
      "properties": {
        "name": "John Doe",
        "age": 30
      }
    }
  ]
}
```

## Data Models

### Entity
```json
{
  "id": "unique_identifier",
  "type": "entity_type",
  "properties": {
    // Key-value pairs of entity properties
  }
}
```

### Relationship
```json
{
  "id": "unique_identifier",
  "type": "relationship_type",
  "start_entity_id": "source_entity_id",
  "end_entity_id": "target_entity_id",
  "properties": {
    // Key-value pairs of relationship properties
  }
}
```

### Query
```json
{
  "cypher": "Cypher query string",
  "parameters": {
    // Query parameters
  }
}
```