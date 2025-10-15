from neo4j import GraphDatabase
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_neo4j_connection():
    # Test with default credentials
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "password"
    
    logger.info(f"Testing Neo4j connection to {uri} with user {user}")
    
    try:
        # Try to connect
        driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Connected to Neo4j successfully")
        
        # Try to run a simple query
        with driver.session() as session:
            result = session.run("RETURN 1 AS num")
            record = result.single()
            if record:
                logger.info(f"Query executed successfully, returned: {record['num']}")
            else:
                logger.error("Query returned no results")
        
        # Close the connection
        driver.close()
        logger.info("Connection closed successfully")
        
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        # If the default password doesn't work, let's try to get the actual password
        # This is just for testing - in a real scenario, you'd get this from config
        logger.info("Trying with neo4j/neo4j as default admin credentials...")
        try:
            driver = GraphDatabase.driver(uri, auth=("neo4j", "neo4j"))
            logger.info("Connected with neo4j/neo4j credentials")
            driver.close()
        except Exception as e2:
            logger.error(f"Failed to connect with neo4j/neo4j: {e2}")

if __name__ == "__main__":
    test_neo4j_connection()