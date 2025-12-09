"""
LEGACY / MIGRATION: Build Knowledge Graph from SQLite Memories (Archived)

This script reads from a legacy SQLite `ece_memory.db` and builds a Neo4j
knowledge graph. It is archived for migration and historical reference.
Active ECE_Core deployments use Neo4j as the primary store and do not depend
on the legacy SQLite database. Run these scripts only for migration in a
staging environment after you have backed up your data and installed `aiosqlite`.

Build Knowledge Graph from SQLite Memories
==========================================
Extracts entities and relationships from existing memories
and populates Neo4j graph for associative retrieval.

Uses local llama.cpp LLM instead of OpenAI.
"""
import asyncio
import json
import re
import sys
from typing import List, Dict, Optional
from datetime import datetime

import aiosqlite
from neo4j import GraphDatabase
import httpx

# Configuration
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # UPDATE THIS!
SQLITE_DB = "../ECE_Core/ece_memory.db"
LLM_ENDPOINT = "http://localhost:8080/v1/chat/completions"  # llama.cpp

# Processing settings
BATCH_SIZE = 10  # Process 10 memories at a time
MAX_MEMORIES = None  # None = all, or set limit for testing


class LocalLLMExtractor:
    """Extract entities using local llama.cpp LLM."""
    
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def extract_entities(self, text: str) -> Dict:
        """
        Extract entities and relationships from text.
        Returns: {entities: [...], relationships: [...]}
        """
        system_prompt = """You are an expert at extracting structured information from text.

Extract entities and relationships. Focus on:
1. **People** - Names of individuals
2. **Concepts** - Important ideas or technologies (ADHD, Memory, Context Cache, etc.)
3. **Projects** - Software projects (ECE_Core, Sovereign CLI, etc.)
4. **Events** - Specific occurrences with dates if mentioned
5. **Relationships** - How entities connect

Return ONLY valid JSON in this format:
{
  "entities": [
    {"type": "Concept", "name": "External Memory"},
    {"type": "Person", "name": "Claude"},
    {"type": "Project", "name": "ECE_Core"}
  ],
  "relationships": [
    {"from": "ECE_Core", "to": "External Memory", "type": "IMPLEMENTS"},
    {"from": "External Memory", "to": "ADHD", "type": "HELPS_WITH"}
  ]
}

Be concise. Extract only the most important entities."""

        # Truncate very long text
        text_sample = text[:2000] if len(text) > 2000 else text
        
        try:
            response = await self.client.post(
                self.endpoint,
                json={
                    "model": "local",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Extract from:\n\n{text_sample}"}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 500
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Try to parse JSON from response
                try:
                    # Sometimes LLM wraps in markdown code blocks
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    
                    extracted = json.loads(content.strip())
                    return extracted
                except json.JSONDecodeError:
                    # Fallback to simple regex extraction
                    return self._fallback_extract(text_sample)
            else:
                return self._fallback_extract(text_sample)
                
        except Exception as e:
            print(f"  LLM extraction failed: {e}, using fallback")
            return self._fallback_extract(text_sample)
    
    def _fallback_extract(self, text: str) -> Dict:
        """Simple regex-based extraction when LLM fails."""
        entities = []
        
        # Extract capitalized words (potential entities)
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        # Common concepts from your domain
        concepts = [
            "ADHD", "Autism", "Memory", "Context", "Cache", "Redis", "SQLite", "Neo4j",
            "Graph", "Markovian", "Reasoning", "ECE", "Dory", "External Memory",
            "Q-Learning", "Context Cache", "Working Memory", "Episodic Memory"
        ]
        
        for word in set(capitalized[:10]):  # Limit to 10
            if len(word) > 2:
                entities.append({"type": "Concept", "name": word})
        
        for concept in concepts:
            if concept.lower() in text.lower():
                entities.append({"type": "Concept", "name": concept})
        
        # Remove duplicates
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e["type"], e["name"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)
        
        return {"entities": unique_entities[:15], "relationships": []}
    
    async def close(self):
        await self.client.aclose()


class Neo4jGraphBuilder:
    """Build and populate Neo4j knowledge graph."""
    
    def __init__(self, uri: str, user: str, password: str):
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("* Neo4j connected")
        except Exception as e:
            print(f"ERROR: Could not connect to Neo4j: {e}")
            print("Make sure Neo4j is running on bolt://localhost:7687")
            print("And update NEO4J_PASSWORD in this script")
            sys.exit(1)
    
    def create_indexes(self):
        """Create indexes for faster lookups."""
        with self.driver.session() as session:
            session.run("CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)")
            session.run("CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)")
            session.run("CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)")
            session.run("CREATE INDEX project_name IF NOT EXISTS FOR (pr:Project) ON (pr.name)")
            session.run("CREATE INDEX memory_id IF NOT EXISTS FOR (m:Memory) ON (m.memory_id)")
        print("* Created Neo4j indexes")
    
    def add_memory_node(self, memory_id: int, category: str, content_preview: str, timestamp: str):
        """Add a memory node to the graph."""
        with self.driver.session() as session:
            session.run("""
                MERGE (m:Memory {memory_id: $memory_id})
                SET m.category = $category,
                    m.preview = $preview,
                    m.timestamp = $timestamp,
                    m.updated = datetime()
            """, memory_id=memory_id, category=category, 
                preview=content_preview[:200], timestamp=timestamp)
    
    def add_entity(self, entity: Dict, memory_id: int):
        """Add entity and link to memory."""
        entity_type = entity.get("type", "Entity")
        name = entity.get("name")
        
        if not name:
            return
        
        with self.driver.session() as session:
            # Create entity node
            session.run(f"""
                MERGE (e:{entity_type} {{name: $name}})
                SET e.updated = datetime()
            """, name=name)
            
            # Link to memory
            session.run(f"""
                MATCH (e:{entity_type} {{name: $name}})
                MATCH (m:Memory {{memory_id: $memory_id}})
                MERGE (m)-[r:MENTIONS]->(e)
                SET r.updated = datetime()
            """, name=name, memory_id=memory_id)
    
    def add_relationship(self, rel: Dict):
        """Add relationship between entities."""
        from_name = rel.get("from")
        to_name = rel.get("to")
        rel_type = rel.get("type", "RELATES_TO").upper().replace(" ", "_")
        
        if not from_name or not to_name:
            return
        
        with self.driver.session() as session:
            # Find or create nodes, add relationship
            session.run(f"""
                MERGE (a:Entity {{name: $from_name}})
                MERGE (b:Entity {{name: $to_name}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r.updated = datetime(),
                    r.q_value = COALESCE(r.q_value, 0.5)
            """, from_name=from_name, to_name=to_name)
    
    def close(self):
        self.driver.close()


async def build_graph():
    """Main function to build knowledge graph from SQLite memories."""
    
    print("\n" + "="*60)
    print("  Knowledge Graph Builder")
    print("  ECE_Core Memory System")
    print("="*60 + "\n")
    
    # Initialize components
    extractor = LocalLLMExtractor(LLM_ENDPOINT)
    graph = Neo4jGraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # Create indexes
        graph.create_indexes()
        
        # Connect to SQLite
        db = await aiosqlite.connect(SQLITE_DB)
        
        # Get total count
        cursor = await db.execute("SELECT COUNT(*) FROM memories")
        total = (await cursor.fetchone())[0]
        
        if MAX_MEMORIES:
            total = min(total, MAX_MEMORIES)
        
        print(f"Processing {total} memories from SQLite...\n")
        
        # Fetch memories in batches
        cursor = await db.execute("""
            SELECT id, category, content, timestamp, tags
            FROM memories
            ORDER BY id
            LIMIT ?
        """, (total,))
        
        memories = await cursor.fetchall()
        processed = 0
        entities_count = 0
        relationships_count = 0
        
        for i in range(0, len(memories), BATCH_SIZE):
            batch = memories[i:i+BATCH_SIZE]
            
            for memory in batch:
                memory_id, category, content, timestamp, tags = memory
                
                # Add memory node to graph
                graph.add_memory_node(memory_id, category, content, timestamp)
                
                # Extract entities
                extracted = await extractor.extract_entities(content)
                
                # Add entities and link to memory
                for entity in extracted.get("entities", []):
                    graph.add_entity(entity, memory_id)
                    entities_count += 1
                
                # Add relationships between entities
                for rel in extracted.get("relationships", []):
                    graph.add_relationship(rel)
                    relationships_count += 1
                
                processed += 1
                
                if processed % 50 == 0:
                    print(f"  Processed {processed}/{total} memories "
                          f"({entities_count} entities, {relationships_count} relationships)")
        
        print(f"\n{'='*60}")
        print(f"GRAPH BUILD COMPLETE!")
        print(f"{'='*60}")
        print(f"  Memories processed:  {processed}")
        print(f"  Entities extracted:  {entities_count}")
        print(f"  Relationships added: {relationships_count}")
        print(f"{'='*60}\n")
        
        # Print sample queries
        print("Try these Cypher queries in Neo4j Browser (http://localhost:7474):\n")
        print("// Find all concepts")
        print("MATCH (c:Concept) RETURN c.name, count(*) as mentions ORDER BY mentions DESC LIMIT 20\n")
        print("// Find what connects to 'ADHD'")
        print("MATCH (a {name: 'ADHD'})-[r]-(b) RETURN b.name, type(r) LIMIT 10\n")
        print("// Find paths between two concepts")
        print("MATCH path = (a {name: 'Dory'})-[*1..3]-(b {name: 'Memory'}) RETURN path LIMIT 5\n")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.close()
        await extractor.close()
        graph.close()


if __name__ == "__main__":
    print("\nNOTE: Make sure Neo4j and llama.cpp are running!")
    print("  Neo4j: http://localhost:7474")
    print("  llama.cpp: http://localhost:8080\n")
    
    input("Press Enter to continue or Ctrl+C to abort...")
    
    asyncio.run(build_graph())
