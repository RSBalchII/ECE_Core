

import graphr1
# from sentence_transformers import SentenceTransformer
import uuid
import logging

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Initialize GraphR1 Client (Singleton pattern) ---
# This ensures we only initialize this object once.
try:
    graph_client = graphr1.Client()
    logging.info("Successfully connected to GraphR1 client.")

except Exception as e:
    logging.error(f"Failed to initialize GraphR1 client: {e}")
    graph_client = None

# --- Tool Functions ---

def store_memory(text_to_store: str) -> dict:
    """
    Stores a piece of text as a memory in the ChromaDB vector store.

    Args:
        text_to_store: The string content of the memory to be stored.

    Returns:
        A dictionary with the status and result of the operation.
    """
    if not graph_client:
        memory_id = str(uuid.uuid4())
        graph_client.nodes.create(id=memory_id, label='MemoryNode', properties={'text': text_to_store, 'source': 'memory_tool'})
        logging.info(f"Successfully stored memory with ID: {memory_id}")
        return {"status": "success", "result": f"Memory stored successfully with ID {memory_id}."}
    except Exception as e:
        logging.error(f"Failed to store memory: {e}")
        return {"status": "error", "result": f"An error occurred while storing memory: {e}"}

def retrieve_similar_memories(query_text: str, num_results: int = 3) -> dict:
    """
    Retrieves memories from ChromaDB that are semantically similar to the query text.

    Args:
        query_text: The text to search for similar memories.
        num_results: The maximum number of memories to retrieve.

    Returns:
        A dictionary with the status and a list of retrieved memories.
    """
    if not graph_client:
        results = graph_client.nodes.search(label='MemoryNode', query=query_text, top_k=num_results)
        retrieved_docs = [node.properties.get('text') for node in results if node.properties.get('text')]
        
        logging.info(f"Retrieved {len(retrieved_docs)} memories for query: '{query_text}'")
        return {"status": "success", "result": retrieved_docs}
    except Exception as e:
        logging.error(f"Failed to retrieve memories: {e}")
        return {"status": "error", "result": f"An error occurred while retrieving memories: {e}"}