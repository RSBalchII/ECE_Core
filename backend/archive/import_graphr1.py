"""
LEGACY: Archive importer with SQLite mid-term storage

This file builds a Graph-R1 knowledge hypergraph from `combined_text.txt` and
includes legacy code that writes summaries to SQLite for quick retrieval.
The script is maintained for historical and migration purposes only; Neo4j is
the primary storage for active ECE_Core deployments. Only run in a staging
environment after backing up your data and installing `aiosqlite`.

Graph-R1 inspired import script for ECE_Core.
Loads combined_text.txt and builds Knowledge HyperGraph in Neo4j.

Based on:
- Graph-R1 paper (n-ary relation extraction + RL retrieval)
- Your existing Neo4j/SQLite storage adapter
- Markovian chunking for memory efficiency
"""
import os
import json
import asyncio
import tiktoken
from datetime import datetime
from typing import List, Dict, Any, Tuple
from neo4j import GraphDatabase
import aiosqlite

# Import your existing components
from memory import TieredMemory
from llm_client import LLMClient
from config import settings


class GraphR1ImportAgent:
    """
    Simplified agent that builds Knowledge HyperGraph from combined_text.txt.
    Uses Markovian chunking + n-ary relation extraction.
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.memory = TieredMemory()
        self.llm = LLMClient()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Markovian chunking params
        self.chunk_size = 2000  # tokens per chunk
        self.overlap = 200      # overlap between chunks
        
    def chunk_text_markovian(self, text: str) -> List[str]:
        """
        Chunk text using Markovian approach:
        - Fixed chunk size
        - Small overlap for continuity
        - Each chunk processed independently
        """
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
            start = end - self.overlap  # Overlap for continuity
            
        return chunks
    
    async def extract_nary_relations(self, chunk: str) -> Dict[str, Any]:
        """
        Extract n-ary relations from chunk.
        
        Graph-R1 uses hypergraph with n-ary relations:
        (entity1, relation, entity2, [additional context entities])
        
        We use LLM to extract these structured relations.
        """
        extraction_prompt = f"""Extract knowledge from this text as structured n-ary relations.
        
Format: JSON with entities and hyperedges.

Example output:
{{
  "entities": [
    {{"id": "e1", "name": "Sybil", "type": "Person"}},
    {{"id": "e2", "name": "Python", "type": "Technology"}}
  ],
  "hyperedges": [
    {{
      "relation": "DISCUSSED",
      "entities": ["e1", "e2"],
      "context": "programming languages",
      "timestamp": "2024-..."
    }}
  ]
}}

Text to extract from:
{chunk[:1500]}

Return ONLY valid JSON:"""
        
        try:
            response = await self.llm.generate(
                prompt=extraction_prompt,
                temperature=0.1,  # Low temp for structured output
                max_tokens=1500
            )
            
            # Parse JSON response
            # Handle potential markdown code blocks
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            data = json.loads(response)
            return data
            
        except Exception as e:
            print(f"Error extracting relations: {e}")
            return {"entities": [], "hyperedges": []}
    
    async def save_to_neo4j(self, extraction: Dict[str, Any], chunk_idx: int):
        """
        Save n-ary relations to Neo4j as knowledge hypergraph.
        
        Graph-R1 approach:
        - Entities as nodes
        - Hyperedges as relationship + context nodes
        """
        if not extraction or not extraction.get("entities"):
            return
            
        with self.driver.session() as session:
            # 1. Create entity nodes
            for entity in extraction.get("entities", []):
                session.run(
                    """
                    MERGE (e:Entity {id: $id})
                    SET e.name = $name, e.type = $type, e.chunk_idx = $chunk_idx
                    """,
                    id=entity.get("id", f"e_{chunk_idx}_{entity.get('name')}"),
                    name=entity.get("name", ""),
                    type=entity.get("type", "Entity"),
                    chunk_idx=chunk_idx
                )
            
            # 2. Create hyperedges (n-ary relations)
            for idx, hedge in enumerate(extraction.get("hyperedges", [])):
                hedge_id = f"h_{chunk_idx}_{idx}"
                relation = hedge.get("relation", "RELATED")
                entities = hedge.get("entities", [])
                context = hedge.get("context", "")
                
                # Create hyperedge node
                session.run(
                    """
                    CREATE (h:HyperEdge {id: $id})
                    SET h.relation = $relation,
                        h.context = $context,
                        h.chunk_idx = $chunk_idx,
                        h.created_at = datetime()
                    """,
                    id=hedge_id,
                    relation=relation,
                    context=context,
                    chunk_idx=chunk_idx
                )
                
                # Connect entities to hyperedge
                for entity_id in entities:
                    session.run(
                        """
                        MATCH (e:Entity {id: $entity_id})
                        MATCH (h:HyperEdge {id: $hedge_id})
                        MERGE (e)-[:PARTICIPATES_IN]->(h)
                        """,
                        entity_id=entity_id,
                        hedge_id=hedge_id
                    )
    
    async def save_summary_to_sqlite(self, chunk: str, extraction: Dict, chunk_idx: int):
        """
        Save chunk summary to SQLite for quick retrieval.
        This is the "warm" memory tier.
        """
        summary = f"Chunk {chunk_idx}: Found {len(extraction.get('entities', []))} entities, {len(extraction.get('hyperedges', []))} relations"
        
        await self.memory.flush_to_sqlite(
            session_id=f"import_{chunk_idx}",
            summary=summary,
            metadata={
                "chunk_idx": chunk_idx,
                "entity_count": len(extraction.get("entities", [])),
                "relation_count": len(extraction.get("hyperedges", []))
            }
        )
    
    async def process_combined_text(self, file_path: str):
        """
        Main import pipeline:
        1. Load combined_text.txt
        2. Chunk using Markovian approach
        3. Extract n-ary relations from each chunk
        4. Save to Neo4j (long-term) and SQLite (mid-term)
        """
        print(f"🚀 Starting Graph-R1 import from {file_path}")
        
        # Initialize memory
        await self.memory.initialize()
        
        # Read file
        print("📖 Reading combined_text.txt...")
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Chunk text
        print("✂️ Chunking text (Markovian)...")
        chunks = self.chunk_text_markovian(text)
        print(f"   Created {len(chunks)} chunks (~{self.chunk_size} tokens each)")
        
        # Process each chunk
        print("\n🔍 Extracting knowledge graph...")
        for idx, chunk in enumerate(chunks):
            print(f"\n📦 Processing chunk {idx + 1}/{len(chunks)}")
            
            # Extract n-ary relations
            extraction = await self.extract_nary_relations(chunk)
            
            # Save to Neo4j
            if extraction.get("entities"):
                print(f"   💾 Saving {len(extraction['entities'])} entities to Neo4j")
                await self.save_to_neo4j(extraction, idx)
            
            # Save summary to SQLite
            await self.save_summary_to_sqlite(chunk, extraction, idx)
            
            # Progress indicator
            if (idx + 1) % 10 == 0:
                print(f"\n⏳ Progress: {idx + 1}/{len(chunks)} chunks ({((idx + 1) / len(chunks)) * 100:.1f}%)")
        
        print("\n✅ Import complete!")
        print(f"   Total chunks processed: {len(chunks)}")
        
        # Close connections
        await self.memory.close()
        await self.llm.close()
        self.driver.close()


async def main():
    """Run the import process."""
    
    # Configuration
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    COMBINED_TEXT_PATH = "combined_text.txt"
    
    if not os.path.exists(COMBINED_TEXT_PATH):
        print(f"❌ Error: {COMBINED_TEXT_PATH} not found!")
        print("   Please ensure combined_text.txt is in the ECE_Core directory.")
        return
    
    # Create agent
    agent = GraphR1ImportAgent(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # Run import
    try:
        await agent.process_combined_text(COMBINED_TEXT_PATH)
    except KeyboardInterrupt:
        print("\n\n⚠️ Import interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during import: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║         Graph-R1 Knowledge HyperGraph Import Tool            ║
║                    ECE_Core v2.0                             ║
╚══════════════════════════════════════════════════════════════╝

This tool will:
1. Load combined_text.txt (your conversations with Sybil/Coda)
2. Extract knowledge using n-ary relations (Graph-R1 approach)
3. Build Knowledge HyperGraph in Neo4j
4. Save summaries to SQLite for fast retrieval

Prerequisites:
- Neo4j running (default: bolt://localhost:7687)
- Redis running
- LLM server running (port 8080)

Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in environment.

Press Ctrl+C to stop at any time.
""")
    
    asyncio.run(main())
