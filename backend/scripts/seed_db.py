import asyncio
import logging
from src.memory.manager import TieredMemory
from src.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_database():
    """Seeds the Neo4j database with an initial 'Genesis' memory."""
    print("🌱 Seeding Neo4j Database...")
    
    store = TieredMemory()
    await store.initialize()
    
    if not store.neo4j_driver:
        print("❌ Failed to connect to Neo4j.")
        return

    try:
        # Create a Genesis memory to establish the Label and Properties
        await store.add_memory(
            session_id="global",
            content="ECE Core System Initialized. This is the Genesis memory node.",
            category="genesis",
            tags=["system", "init"],
            importance=10,
            metadata={"version": "1.0.0", "author": "Antigravity"}
        )
        print("✅ Genesis memory created successfully.")
        print("   - Label 'Memory' created.")
        print("   - Properties 'category', 'content', 'session_id', 'created_at' initialized.")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
    finally:
        await store.close()
        print("👋 Connection closed.")

if __name__ == "__main__":
    asyncio.run(seed_database())
