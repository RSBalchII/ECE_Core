from neo4j import GraphDatabase

class Neo4jSchemaInitializer:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def clear_database(self):
        """Wipe the entire database including schema."""
        with self.driver.session() as session:
            # Delete data
            session.run("MATCH (n) DETACH DELETE n")
            
            # Drop all constraints
            constraints = session.run("SHOW CONSTRAINTS").data()
            for constraint in constraints:
                name = constraint.get("name")
                if name:
                    session.run(f"DROP CONSTRAINT {name}")
            
            # Drop all indexes
            indexes = session.run("SHOW INDEXES").data()
            for index in indexes:
                name = index.get("name")
                # Skip internal indexes if any, usually names are enough
                if name and "LOOKUP" not in index.get("type", ""): 
                    session.run(f"DROP INDEX {name}")
                    
            print("Database cleared (Data, Constraints, Indexes).")

    def initialize_schema(self):
        with self.driver.session() as session:
            session.execute_write(self._create_memory_node)
            session.execute_write(self._create_entity_node)
            session.execute_write(self._create_moment_node)
            session.execute_write(self._create_relationships)
            session.execute_write(self._create_indexes)

    @staticmethod
    def _create_memory_node(tx):
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE")

    @staticmethod
    def _create_entity_node(tx):
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")

    @staticmethod
    def _create_moment_node(tx):
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (mo:Moment) REQUIRE mo.id IS UNIQUE")

    @staticmethod
    def _create_relationships(tx):
        # No explicit schema needed for relationships in Neo4j 5, but we can ensure existence of types via a dummy creation
        tx.run("MERGE ()-[r:CONTAINS]->()")
        tx.run("MERGE ()-[r:NEXT]->()")

from neo4j import GraphDatabase

class Neo4jSchemaInitializer:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def clear_database(self):
        """Wipe the entire database including schema."""
        with self.driver.session() as session:
            # Delete data
            session.run("MATCH (n) DETACH DELETE n")
            
            # Drop all constraints
            constraints = session.run("SHOW CONSTRAINTS").data()
            for constraint in constraints:
                name = constraint.get("name")
                if name:
                    session.run(f"DROP CONSTRAINT {name}")
            
            # Drop all indexes
            indexes = session.run("SHOW INDEXES").data()
            for index in indexes:
                name = index.get("name")
                # Skip internal indexes if any, usually names are enough
                if name and "LOOKUP" not in index.get("type", ""): 
                    session.run(f"DROP INDEX {name}")
                    
            print("Database cleared (Data, Constraints, Indexes).")

    def initialize_schema(self):
        with self.driver.session() as session:
            session.execute_write(self._create_memory_node)
            session.execute_write(self._create_entity_node)
            session.execute_write(self._create_moment_node)
            session.execute_write(self._create_relationships)
            session.execute_write(self._create_indexes)

    @staticmethod
    def _create_memory_node(tx):
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE")

    @staticmethod
    def _create_entity_node(tx):
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")

    @staticmethod
    def _create_moment_node(tx):
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (mo:Moment) REQUIRE mo.id IS UNIQUE")

    @staticmethod
    def _create_relationships(tx):
        # No explicit schema needed for relationships in Neo4j 5, but we can ensure existence of types via a dummy creation
        tx.run("MERGE ()-[r:CONTAINS]->()")
        tx.run("MERGE ()-[r:NEXT]->()")

    @staticmethod
    def _create_indexes(tx):
        tx.run("CREATE FULLTEXT INDEX memorySearch IF NOT EXISTS FOR (m:Memory) ON EACH [m.content, m.tags]")
        tx.run("CREATE FULLTEXT INDEX entitySearch IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.description]")
        tx.run("CREATE FULLTEXT INDEX momentSearch IF NOT EXISTS FOR (mo:Moment) ON EACH [mo.summary]")

if __name__ == "__main__":
    from src.config import settings
    initializer = Neo4jSchemaInitializer(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    initializer.clear_database()  # Wipe first
    initializer.initialize_schema()
    initializer.close()