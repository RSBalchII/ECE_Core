"""Test embedded Neo4j startup."""
import time
from src.utils.neo4j_embedded import EmbeddedNeo4j
from neo4j import GraphDatabase

def test_embedded_neo4j():
    """Test that Neo4j starts and accepts connections."""
    print("Testing embedded Neo4j...")
    
    # Start Neo4j
    neo4j = EmbeddedNeo4j()
    success = neo4j.start()
    
    if not success:
        print("❌ Failed to start Neo4j")
        return False
    
    # Try to connect
    try:
        print(f"Connecting to {neo4j.get_bolt_uri()}...")
        driver = GraphDatabase.driver(neo4j.get_bolt_uri(), auth=None)
        
        # Test simple query
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            print(f"✓ Connection successful! Test query returned: {record['test']}")
        
        driver.close()
        
        # Test creating a node
        driver = GraphDatabase.driver(neo4j.get_bolt_uri(), auth=None)
        with driver.session() as session:
            session.run("CREATE (n:TestNode {name: 'ECE_Core Test', timestamp: datetime()})")
            result = session.run("MATCH (n:TestNode) RETURN count(n) as count")
            count = result.single()['count']
            print(f"✓ Created test node. Total test nodes: {count}")
        
        driver.close()
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    
    finally:
        print("\nStopping Neo4j...")
        neo4j.stop()
        print("✓ Neo4j stopped")
    
    return True

if __name__ == "__main__":
    test_embedded_neo4j()
