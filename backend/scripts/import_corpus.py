import uuid
import os
import argparse
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from src.distiller import Distiller
from neo4j import GraphDatabase

# Configuration
COMBINED_TEXT_PATH = Path(__file__).parent.parent / "combined_text.txt"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

# Simple chunking: split by double newline and limit size
def chunk_text(text, max_chars=2000):
    chunks = []
    current = []
    current_len = 0
    for paragraph in text.split("\n\n"):
        para = paragraph.strip()
        if not para:
            continue
        if current_len + len(para) + 2 > max_chars:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks

async def main():
    parser = argparse.ArgumentParser(description="Import corpus into Neo4j")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM for verification")
    args = parser.parse_args()

    if not COMBINED_TEXT_PATH.exists():
        raise FileNotFoundError(f"Combined text file not found at {COMBINED_TEXT_PATH}")
    text = COMBINED_TEXT_PATH.read_text(encoding="utf-8")
    chunks = chunk_text(text)
    
    # DEBUG: Limit to 5 chunks for verification
    chunks = chunks[:5]
    print(f"Importing {len(chunks)} chunks into Neo4j (Limited for verification)")
    if args.mock:
        print("⚠️  RUNNING IN MOCK MODE - No actual LLM calls will be made")

    # Initialize LLM Client for Distiller
    if args.mock:
        llm = MagicMock()
        llm.generate = AsyncMock(return_value='{"summary": "Mock Summary", "entities": [{"name": "MockEntity", "type": "Concept", "description": "A mock entity"}]}')
    else:
        from src.llm import LLMClient
        llm = LLMClient()
        
    distiller = Distiller(llm)
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Verify connection
    try:
        driver.verify_connectivity()
        print("Connected to Neo4j")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return

    with driver.session() as session:
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")
            try:
                moment_data = await distiller.distill_moment(chunk, chunk_index=i+1, total_chunks=len(chunks))
                moment_id = str(uuid.uuid4())
                summary = moment_data.get("summary", "")
                
                # Create Moment node
                session.run(
                    "MERGE (m:Moment {id: $id}) SET m.summary = $summary",
                    id=moment_id,
                    summary=summary,
                )
                # If entities extracted, create them and link
                entities = moment_data.get("entities", [])
                for ent in entities:
                    name = ent.get("name")
                    description = ent.get("description", "")
                    session.run(
                        "MERGE (e:Entity {name: $name}) SET e.description = $desc",
                        name=name,
                        desc=description,
                    )
                    session.run(
                        "MATCH (m:Moment {id: $mid}), (e:Entity {name: $ename}) "
                        "MERGE (m)-[:CONTAINS]->(e)",
                        mid=moment_id,
                        ename=name,
                    )
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                
    driver.close()
    print("Import completed.")

if __name__ == "__main__":
    asyncio.run(main())
