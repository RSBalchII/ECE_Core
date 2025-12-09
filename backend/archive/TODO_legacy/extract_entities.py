"""
LEGACY (ARCHIVED)
This file was moved to `archive/legacy_sqlite/extract_entities.py`.
The project is now Neo4j-first; the original SQLite-backed extractor remains
in the archive for reference only.
"""

print("This file is archived. See archive/legacy_sqlite/extract_entities.py")
import asyncio
import aiosqlite
import json
from typing import List, Dict, Set, Tuple
from llm_client import LLMClient
from config import DB_PATH

# Optional Neo4j
try:
    from neo4j import AsyncGraphDatabase
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False
    print("⚠️  neo4j package not installed. Run: pip install neo4j")


class EntityExtractor:
    """Extract entities and relations from conversation memories"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.db = None
        self.llm = LLMClient()
        self.neo4j_driver = None
    
    async def initialize(self):
        """Connect to databases"""
        self.db = await aiosqlite.connect(self.db_path)
        await self._ensure_entity_tables()
    
    async def _ensure_entity_tables(self):
        """Create entity tables in SQLite if they don't exist"""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                type TEXT,
                first_seen DATETIME,
                mention_count INTEGER DEFAULT 1
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS turn_entities (
                turn_id INTEGER,
                entity_id INTEGER,
                FOREIGN KEY(turn_id) REFERENCES conversation_turns(id),
                FOREIGN KEY(entity_id) REFERENCES entities(id)
            )
        """)
        
        await self.db.commit()
    
    def connect_neo4j(self, uri: str, user: str, password: str):
        """Connect to Neo4j (optional but recommended)"""
        if not HAS_NEO4J:
            print("⚠️  Neo4j not available")
            return False
        
        self.neo4j_driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        return True
    
    async def extract_entities_from_turn(self, turn_id: int, content: str, speaker: str) -> List[Dict]:
        """
        Use LLM to extract entities from a conversation turn.
        
        Returns list of: {name: str, type: str}
        """
        prompt = f"""Extract key entities from this conversation turn.
Entity types: PERSON, CONCEPT, PROJECT, CONDITION, SKILL

Speaker: {speaker}
Content: {content}

Return JSON array of entities:
[{{"name": "entity_name", "type": "PERSON|CONCEPT|..."}}]

Only extract meaningful, specific entities. Omit generic words.
JSON:"""
        
        try:
            response = await self.llm.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=300
            )
            
            # Parse JSON from response
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            entities = json.loads(response.strip())
            
            # Validate structure
            if isinstance(entities, list):
                return [e for e in entities if "name" in e and "type" in e]
            else:
                return []
        
        except Exception as e:
            print(f"⚠️  Entity extraction failed for turn {turn_id}: {e}")
            return []
    
    async def store_entity(self, name: str, entity_type: str, turn_id: int) -> int:
        """
        Store entity in SQLite, return entity_id.
        Creates new entity or updates mention count.
        """
        # Check if exists
        cursor = await self.db.execute(
            "SELECT id, mention_count FROM entities WHERE name = ?",
            (name,)
        )
        row = await cursor.fetchone()
        
        if row:
            entity_id = row[0]
            mention_count = row[1] + 1
            await self.db.execute(
                "UPDATE entities SET mention_count = ? WHERE id = ?",
                (mention_count, entity_id)
            )
        else:
            # Get turn timestamp
            cursor = await self.db.execute(
                "SELECT timestamp FROM conversation_turns WHERE id = ?",
                (turn_id,)
            )
            timestamp_row = await cursor.fetchone()
            timestamp = timestamp_row[0] if timestamp_row else None
            
            cursor = await self.db.execute(
                "INSERT INTO entities (name, type, first_seen) VALUES (?, ?, ?)",
                (name, entity_type, timestamp)
            )
            entity_id = cursor.lastrowid
        
        # Link turn to entity
        await self.db.execute(
            "INSERT INTO turn_entities (turn_id, entity_id) VALUES (?, ?)",
            (turn_id, entity_id)
        )
        
        await self.db.commit()
        return entity_id
    
    async def create_neo4j_entity(self, entity_id: int, name: str, entity_type: str, sqlite_turn_ids: List[int]):
        """
        Create or update entity in Neo4j with references to SQLite turn IDs.
        This is the key link: Neo4j stores structure, SQLite stores content.
        """
        if not self.neo4j_driver:
            return
        
        async with self.neo4j_driver.session() as session:
            await session.run(
                """
                MERGE (e:Entity {id: $entity_id})
                SET e.name = $name,
                    e.type = $type,
                    e.sqlite_turn_ids = $turn_ids
                """,
                entity_id=f"ent_{entity_id}",
                name=name,
                type=entity_type,
                turn_ids=sqlite_turn_ids
            )
    
    async def create_neo4j_relation(self, turn_id: int, entity_ids: List[int], relation_type: str, context: str):
        """
        Create n-ary relation (HyperEdge) in Neo4j.
        Links multiple entities that appeared together in a turn.
        """
        if not self.neo4j_driver or len(entity_ids) < 2:
            return
        
        async with self.neo4j_driver.session() as session:
            # Create hyperedge
            hedge_id = f"hedge_{turn_id}"
            
            await session.run(
                """
                CREATE (h:HyperEdge {id: $hedge_id})
                SET h.relation = $relation,
                    h.context = $context,
                    h.sqlite_turn_id = $turn_id
                """,
                hedge_id=hedge_id,
                relation=relation_type,
                context=context,
                turn_id=turn_id
            )
            
            # Connect entities to hyperedge
            for entity_id in entity_ids:
                await session.run(
                    """
                    MATCH (e:Entity {id: $entity_id})
                    MATCH (h:HyperEdge {id: $hedge_id})
                    MERGE (e)-[:PARTICIPATES_IN]->(h)
                    """,
                    entity_id=f"ent_{entity_id}",
                    hedge_id=hedge_id
                )
    
    async def process_turn(self, turn_id: int, content: str, speaker: str) -> Dict:
        """
        Extract entities from a turn and store in both SQLite and Neo4j.
        """
        # Extract entities using LLM
        entities = await self.extract_entities_from_turn(turn_id, content, speaker)
        
        if not entities:
            return {"turn_id": turn_id, "entities_extracted": 0}
        
        # Store in SQLite and collect entity IDs
        entity_ids = []
        for ent in entities:
            ent_id = await self.store_entity(ent["name"], ent["type"], turn_id)
            entity_ids.append(ent_id)
        
        # Create Neo4j entities
        if self.neo4j_driver:
            for i, ent_id in enumerate(entity_ids):
                ent_name = entities[i]["name"]
                ent_type = entities[i]["type"]
                await self.create_neo4j_entity(ent_id, ent_name, ent_type, [turn_id])
            
            # Create relation (hyperedge) connecting entities in this turn
            if len(entity_ids) >= 2:
                relation_type = f"{speaker}_mentioned"
                await self.create_neo4j_relation(turn_id, entity_ids, relation_type, content[:200])
        
        return {
            "turn_id": turn_id,
            "entities_extracted": len(entities),
            "entities": entities
        }
    
    async def extract_all_turns(self, limit: int = None):
        """
        Process all turns in the database and extract entities.
        This populates both SQLite entities tables and Neo4j graph.
        """
        query = "SELECT id, content, speaker FROM conversation_turns ORDER BY id"
        if limit:
            query += f" LIMIT {limit}"
        
        cursor = await self.db.execute(query)
        turns = await cursor.fetchall()
        
        print(f"🔄 Processing {len(turns)} turns for entity extraction...")
        
        results = []
        for i, (turn_id, content, speaker) in enumerate(turns, 1):
            if i % 10 == 0:
                print(f"   Progress: {i}/{len(turns)} turns")
            
            result = await self.process_turn(turn_id, content, speaker)
            results.append(result)
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.1)
        
        total_entities = sum(r["entities_extracted"] for r in results)
        print(f"\n✅ Extraction complete!")
        print(f"   Total entities: {total_entities}")
        print(f"   Avg per turn: {total_entities/len(turns):.1f}")
        
        return results
    
    async def get_entity_summary(self) -> Dict:
        """Get summary of extracted entities"""
        cursor = await self.db.execute("""
            SELECT type, COUNT(*) as count
            FROM entities
            GROUP BY type
            ORDER BY count DESC
        """)
        
        by_type = {row[0]: row[1] for row in await cursor.fetchall()}
        
        cursor = await self.db.execute("SELECT COUNT(*) FROM entities")
        total = (await cursor.fetchone())[0]
        
        cursor = await self.db.execute("SELECT COUNT(*) FROM turn_entities")
        total_mentions = (await cursor.fetchone())[0]
        
        return {
            "total_entities": total,
            "total_mentions": total_mentions,
            "by_type": by_type
        }
    
    async def close(self):
        """Close database connections"""
        if self.db:
            await self.db.close()
        if self.neo4j_driver:
            await self.neo4j_driver.close()


async def main():
    """Run entity extraction"""
    import os
    
    print("=" * 60)
    print("  Entity Extraction for ECE_Core")
    print("=" * 60)
    
    extractor = EntityExtractor()
    await extractor.initialize()
    
    # Connect to Neo4j if available
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    
    if neo4j_password:
        print(f"🔗 Connecting to Neo4j: {neo4j_uri}")
        extractor.connect_neo4j(neo4j_uri, neo4j_user, neo4j_password)
    else:
        print("⚠️  No Neo4j credentials - only updating SQLite entities")
    
    # Process turns (start with small batch for testing)
    print("\n📝 Starting extraction (testing with 20 turns)...")
    await extractor.extract_all_turns(limit=20)
    
    # Show summary
    print("\n📊 Entity Summary:")
    summary = await extractor.get_entity_summary()
    print(f"   Total unique entities: {summary['total_entities']}")
    print(f"   Total mentions: {summary['total_mentions']}")
    print(f"   By type:")
    for entity_type, count in summary['by_type'].items():
        print(f"      {entity_type}: {count}")
    
    await extractor.close()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
