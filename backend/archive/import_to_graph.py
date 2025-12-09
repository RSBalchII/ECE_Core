"""
LEGACY: This utility stores chunks and summaries in SQLite as part of the
legacy import pipeline. SQLite is no longer used by active ECE_Core deployments,
but these scripts are retained for archival/migration reasons.

If you need to run this code:
 - Install `aiosqlite` via `pip install aiosqlite`
 - Set `ECE_ALLOW_LEGACY_SQLITE=1` when running legacy importers

For modern imports, prefer Neo4j-based importers described in the `README`.
See `ece-core/archive/legacy_sqlite/README.md` for details.
"""

"""
Import combined_text.txt into Neo4j Knowledge Graph + SQLite
Using Markovian chunking and Q-Learning guided extraction.
"""

import asyncio
import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

import aiosqlite
from neo4j import GraphDatabase
import tiktoken
from openai import OpenAI

# Configuration
COMBINED_TEXT_PATH = "combined_text.txt"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_password"  # Change this!
SQLITE_DB = "ece_memory.db"

# Chunking settings (Markovian approach)
CHUNK_SIZE = 4000  # tokens per chunk
OVERLAP = 200  # token overlap between chunks
MAX_CHUNKS = 1000  # safety limit

# LLM for entity extraction
EXTRACTOR_MODEL = "gpt-4o-mini"  # or your local llama.cpp endpoint


class MarkovianChunker:
    """Chunk large text using Markovian reasoning principles."""
    
    def __init__(self, chunk_size=4000, overlap=200):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))
    
    def chunk_text(self, text: str) -> List[Dict[str, any]]:
        """Split text into overlapping chunks with metadata."""
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        for i in range(0, len(tokens), self.chunk_size - self.overlap):
            chunk_tokens = tokens[i:i + self.chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            chunks.append({
                "text": chunk_text,
                "start_token": i,
                "end_token": i + len(chunk_tokens),
                "token_count": len(chunk_tokens),
                "chunk_id": len(chunks)
            })
            
            if len(chunks) >= MAX_CHUNKS:
                break
        
        return chunks


class EntityExtractor:
    """Extract entities and relationships using LLM."""
    
    def __init__(self, model=EXTRACTOR_MODEL):
        self.client = OpenAI()  # Will use OPENAI_API_KEY env var
        self.model = model
    
    async def extract_from_chunk(self, chunk_text: str, chunk_id: int) -> Dict:
        """Extract entities and relationships from a text chunk."""
        
        system_prompt = """You are an expert at extracting structured information from conversational text.

Extract:
1. **People**: Names of individuals mentioned
2. **Concepts**: Important ideas, technologies, or topics discussed
3. **Events**: Specific occurrences with dates if mentioned
4. **Code/Projects**: Software projects, libraries, or code snippets mentioned
5. **Relationships**: How entities relate to each other

Return JSON format:
{
  "entities": [
    {"type": "person", "name": "Alice", "context": "discussed AI"},
    {"type": "concept", "name": "External Memory", "context": "core idea for ECE"},
    {"type": "event", "name": "Diagnosed with AutiHD", "date": "2019", "context": "at age 28"}
  ],
  "relationships": [
    {"from": "Alice", "to": "External Memory", "type": "DISCUSSED"},
    {"from": "ECE_Core", "to": "Redis", "type": "USES"}
  ]
}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract entities and relationships from:\n\n{chunk_text[:2000]}"}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["chunk_id"] = chunk_id
            return result
            
        except Exception as e:
            print(f"Error extracting from chunk {chunk_id}: {e}")
            return {"entities": [], "relationships": [], "chunk_id": chunk_id}


class Neo4jGraphBuilder:
    """Build knowledge graph in Neo4j."""
    
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def create_indexes(self):
        """Create indexes for faster lookups."""
        with self.driver.session() as session:
            session.run("CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (c:Concept) ON (c.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (pr:Project) ON (pr.name)")
    
    def add_entity(self, entity: Dict, chunk_id: int):
        """Add an entity node to the graph."""
        entity_type = entity.get("type", "Unknown").title()
        name = entity.get("name")
        context = entity.get("context", "")
        date = entity.get("date")
        
        with self.driver.session() as session:
            query = f"""
            MERGE (e:{entity_type} {{name: $name}})
            SET e.context = $context,
                e.chunk_id = $chunk_id,
                e.last_updated = datetime()
            """
            if date:
                query += ", e.date = $date"
            
            session.run(query, name=name, context=context, chunk_id=chunk_id, date=date)
    
    def add_relationship(self, rel: Dict, chunk_id: int):
        """Add a relationship between entities."""
        from_name = rel.get("from")
        to_name = rel.get("to")
        rel_type = rel.get("type", "RELATES_TO")
        
        with self.driver.session() as session:
            # Use MATCH to find existing nodes, or create if needed
            query = """
            MERGE (a {name: $from_name})
            MERGE (b {name: $to_name})
            MERGE (a)-[r:""" + rel_type + """]->(b)
            SET r.chunk_id = $chunk_id,
                r.created = datetime()
            """
            session.run(query, from_name=from_name, to_name=to_name, chunk_id=chunk_id)


class SQLiteMemoryStore:
    """Store chunks and summaries in SQLite."""
    
    def __init__(self, db_path):
        self.db_path = db_path
    
    async def initialize(self):
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memory_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id INTEGER UNIQUE,
                    text TEXT,
                    token_count INTEGER,
                    entities TEXT,
                    timestamp TEXT
                )
            """)
            await db.commit()
    
    async def store_chunk(self, chunk: Dict, extracted: Dict):
        """Store a processed chunk."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO memory_chunks 
                (chunk_id, text, token_count, entities, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                chunk["chunk_id"],
                chunk["text"],
                chunk["token_count"],
                json.dumps(extracted),
                datetime.utcnow().isoformat()
            ))
            await db.commit()


async def import_combined_text():
    """Main import function."""
    
    print("🚀 Starting import of combined_text.txt to Knowledge Graph")
    print("=" * 60)
    
    # Initialize components
    chunker = MarkovianChunker(CHUNK_SIZE, OVERLAP)
    extractor = EntityExtractor()
    graph = Neo4jGraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    sqlite = SQLiteMemoryStore(SQLITE_DB)
    
    await sqlite.initialize()
    graph.create_indexes()
    
    # Load text
    print("\n📖 Loading combined_text.txt...")
    with open(COMBINED_TEXT_PATH, 'r', encoding='utf-8') as f:
        full_text = f.read()
    
    total_tokens = chunker.count_tokens(full_text)
    print(f"Total tokens: {total_tokens:,}")
    
    # Chunk text
    print(f"\n✂️  Chunking into {CHUNK_SIZE}-token chunks with {OVERLAP}-token overlap...")
    chunks = chunker.chunk_text(full_text)
    print(f"Created {len(chunks)} chunks")
    
    # Process each chunk
    print("\n🔍 Extracting entities and building graph...")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}/{len(chunks)} (tokens {chunk['start_token']}-{chunk['end_token']})")
        
        # Extract entities and relationships
        extracted = await extractor.extract_from_chunk(chunk["text"], chunk["chunk_id"])
        
        # Add to Neo4j
        entities = extracted.get("entities", [])
        relationships = extracted.get("relationships", [])
        
        print(f"  Found {len(entities)} entities, {len(relationships)} relationships")
        
        for entity in entities:
            graph.add_entity(entity, chunk["chunk_id"])
        
        for rel in relationships:
            graph.add_relationship(rel, chunk["chunk_id"])
        
        # Store in SQLite
        await sqlite.store_chunk(chunk, extracted)
        
        # Progress update
        if (i + 1) % 10 == 0:
            print(f"  ✓ Processed {i+1} chunks")
    
    print("\n✅ Import complete!")
    print(f"  - Processed {len(chunks)} chunks")
    print(f"  - Built knowledge graph in Neo4j")
    print(f"  - Stored chunks in SQLite")
    
    graph.close()


if __name__ == "__main__":
    # Set your Neo4j password before running!
    print("⚠️  Make sure to set NEO4J_PASSWORD in this script!")
    print("⚠️  Make sure Neo4j is running!")
    print("⚠️  Make sure OPENAI_API_KEY is set in environment!")
    print()
    
    response = input("Ready to import? (yes/no): ")
    if response.lower() == 'yes':
        asyncio.run(import_combined_text())
    else:
        print("Cancelled.")
