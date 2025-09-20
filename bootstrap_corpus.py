# ECE/External-Context-Engine-ECE/bootstrap_corpus.py (MODIFIED)
import httpx
import os
import asyncio
import json
from datetime import datetime  # Add datetime import
from rich.console import Console
from ece.agents.tier3.injector.db_manager import Neo4jManager  # Correct import

# --- Configuration --- (unchanged)
ORCHESTRATOR_URL = "http://localhost:8000/process_prompt"
CORPUS_FILE_PATH = "combined_text.txt"
CHUNK_SIZE = 4500
STATE_FILE = "bootstrap_state.json"
# ---------------------

def load_state():
    """Loads the last successfully processed chunk index from the state file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return json.load(f).get("last_completed_chunk", -1)
            except json.JSONDecodeError:
                return -1
    return -1

def save_state(chunk_index):
    """Saves the index of the last successfully processed chunk."""
    with open(STATE_FILE, 'w') as f:
        json.dump({"last_completed_chunk": chunk_index}, f)

async def bootstrap_corpus():
    """
    Reads a large text corpus, breaks it into chunks, and sends each chunk
    to the ECE Orchestrator, with the ability to resume after interruption.
    """
    console = Console()
    console.print(f"[bold green]Starting corpus bootstrapping process...[/bold green]")

    # === NEW CODE: Initialize Neo4jManager with correct connection details ===
    neo4j_manager = Neo4jManager(
        uri="bolt://neo4j:7687",  # Use the service name from docker-compose.yml
        user="neo4j",
        password="password"
    )
    neo4j_manager.connect()
    # === END NEW CODE ===

    try:
        with open(CORPUS_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            full_text = f.read()
    except FileNotFoundError:
        console.print(f"[bold red]Error: The file '{CORPUS_FILE_PATH}' was not found.[/bold red]")
        return

    chunks = [full_text[i:i + CHUNK_SIZE] for i in range(0, len(full_text), CHUNK_SIZE)]
    num_chunks = len(chunks)
    console.print(f"Corpus contains {num_chunks} total chunks.")

    last_completed_chunk = load_state()
    start_chunk = last_completed_chunk + 1

    if start_chunk > 0:
        console.print(f"[bold yellow]Resuming from chunk {start_chunk + 1} of {num_chunks}...[/bold yellow]")

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i in range(start_chunk, num_chunks):
            chunk = chunks[i]
            console.print(f"\n[yellow]Processing chunk {i + 1} of {num_chunks}...[/yellow]")
            
            prompt = f"BOOTSTRAP_DISTILL: {chunk}"
            # Use GET method with query parameters for the orchestrator endpoint
            try:
                response = await client.get(ORCHESTRATOR_URL, params={"prompt": prompt})
                
                if response.status_code == 200:
                    console.print(f"[green]Chunk {i + 1} successfully processed.[/green]")
                    # Save progress only on success
                    save_state(i)
                    
                    # === NEW CODE: Write processed data to Neo4j ===
                    processed_data = response.json().get("response", "")
                    if processed_data:
                        # Create a simple entity structure for the processed data
                        data = {
                            "entities": [
                                {
                                    "id": f"context_chunk_{i+1}",
                                    "type": "ContextChunk",
                                    "properties": {
                                        "content": str(processed_data),
                                        "chunk_number": i+1,
                                        "timestamp": str(datetime.now().isoformat())
                                    }
                                }
                            ],
                            "summary": str(processed_data)[:100] + "..." if len(str(processed_data)) > 100 else str(processed_data)
                        }
                        # Translate to Cypher queries and execute transaction
                        cypher_queries = neo4j_manager._translate_to_cypher(data)
                        if cypher_queries:
                            neo4j_manager.execute_transaction(cypher_queries)
                    # === END NEW CODE ===
                else:
                    console.print(f"[bold red]Error on chunk {i + 1}:[/bold red] HTTP {response.status_code} - {response.text}")
                    console.print("[bold yellow]Stopping. You can restart the script to resume from this point.[/bold yellow]")
                    return # Stop on error
                
                await asyncio.sleep(0.5)

            except httpx.RequestError:
                console.print(f"[bold red]Connection Error on chunk {i + 1}.[/bold red]")
                console.print("[bold yellow]Stopping. You can restart the script to resume.[/bold yellow]")
                return
            except Exception as e:
                console.print(f"[bold red]An unexpected error occurred with chunk {i + 1}: {e}[/bold red]")
                return

    console.print(f"\n[bold green]Corpus bootstrapping complete. All {num_chunks} chunks processed.[/bold green]")
    # Clean up state file on successful completion
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)

if __name__ == "__main__":
    asyncio.run(bootstrap_corpus())