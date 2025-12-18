
import asyncio
import os
import sys
from neo4j import AsyncGraphDatabase

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def check_memory():
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "password" # Default, might need to check config
    
    # Read config to get actual credentials
    try:
        with open("backend/config.yaml", "r") as f:
            import yaml
            config = yaml.safe_load(f)
            # Assuming config structure, but let's try default first or env vars
            pass
    except:
        pass

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    query = """
    MATCH (m:Memory)
    WHERE m.content CONTAINS 'Context Engine'
    RETURN m.content, m.category, m.created_at
    ORDER BY m.created_at DESC
    LIMIT 5
    """
    
    try:
        async with driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            print(f"Found {len(records)} memories:")
            for r in records:
                print(f"- [{r['m.category']}] {r['m.content'][:100]}...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_memory())
