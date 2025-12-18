#!/usr/bin/env python3
"""
Export Neo4j Memory Nodes to Sovereign JSON Format

This script connects to your running Neo4j instance and exports all Memory nodes
in a format compatible with the Sovereign Memory Builder (CozoDB WASM).

Usage:
    python export_neo4j_to_sovereign.py --output combined_memory.json

Output Format:
    [
        {"id": "uuid-1", "timestamp": 1753..., "role": "user", "content": "...", "source": "neo4j"},
        {"id": "uuid-2", "timestamp": 1753..., "role": "assistant", "content": "...", "source": "neo4j"},
        ...
    ]

The output file can be dragged into the Sovereign Memory Builder for ingestion.
"""

import asyncio
import json
import sys
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable
except ImportError:
    print("ERROR: neo4j package not installed. Run: pip install neo4j")
    sys.exit(1)

# === CONFIGURATION ===
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # UPDATE IF NEEDED

DEFAULT_OUTPUT = "combined_memory.json"


class Neo4jExporter:
    """Export memories from Neo4j to Sovereign JSON format."""
    
    def __init__(self, uri: str, user: str, password: str):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.memories: List[Dict] = []
    
    def connect(self) -> bool:
        """Connect to Neo4j and verify connectivity."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=10.0
            )
            # Verify connectivity
            with self.driver.session() as session:
                session.run("RETURN 1")
            print(f"✓ Connected to Neo4j: {self.uri}")
            return True
        except ServiceUnavailable:
            print(f"✗ Neo4j unavailable at {self.uri}")
            print("  Ensure Neo4j is running: sudo systemctl start neo4j")
            return False
        except Exception as e:
            print(f"✗ Neo4j connection failed: {e}")
            return False
    
    def export_memories(self) -> List[Dict]:
        """
        Query all Memory nodes from Neo4j and convert to Sovereign format.
        
        Expected Neo4j properties:
            - id: Node id (auto-generated, will be stringified)
            - content: Message/session text (string)
            - created_at: ISO 8601 timestamp OR Unix epoch (int/float)
            - category: Content category (inferred as 'user' if not 'system')
            - metadata: JSON string or dict with source info (optional)
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")
        
        query = """
        MATCH (m:Memory)
        RETURN 
            id(m) AS node_id,
            m.content AS content,
            m.created_at AS created_at,
            m.category AS category,
            m.metadata AS metadata
        ORDER BY m.created_at DESC
        """
        
        memories = []
        try:
            with self.driver.session() as session:
                result = session.run(query)
                
                for record in result:
                    memory = self._convert_record(record)
                    if memory:
                        memories.append(memory)
                        if len(memories) % 10 == 0:
                            print(f"  Exported {len(memories)} memories...")
        
        except Exception as e:
            print(f"✗ Query failed: {e}")
            return []
        
        self.memories = memories
        return memories
    
    def _convert_record(self, record) -> Optional[Dict]:
        """Convert a Neo4j record to Sovereign format."""
        try:
            # Extract fields (use node_id since Memory doesn't have an explicit id property)
            mem_id = record.get("node_id")
            content = record.get("content")
            created_at = record.get("created_at")
            category = record.get("category", "user")  # Default to 'user' if missing
            metadata = record.get("metadata", {})
            
            # Validate required fields
            if mem_id is None or not content:
                print(f"  ⚠ Skipping memory: missing node_id or content")
                return None
            
            # Convert timestamp to Unix milliseconds
            timestamp = self._parse_timestamp(created_at)
            if timestamp is None:
                print(f"  ⚠ Skipping memory {mem_id}: invalid timestamp {created_at}")
                return None
            
            # Determine role based on category
            # category can be things like "user_input", "system", "assistant_response", etc.
            role = "user"
            if category and isinstance(category, str):
                if "assistant" in category.lower() or "response" in category.lower():
                    role = "assistant"
                elif "system" in category.lower():
                    role = "system"
            
            # Parse metadata if it's a JSON string
            source = "neo4j"
            if isinstance(metadata, str):
                try:
                    metadata_dict = json.loads(metadata)
                    source = metadata_dict.get("source", "neo4j")
                except json.JSONDecodeError:
                    pass
            elif isinstance(metadata, dict):
                source = metadata.get("source", "neo4j")
            
            return {
                "id": str(mem_id),
                "timestamp": int(timestamp),
                "role": role,
                "content": str(content),
                "source": source
            }
        
        except Exception as e:
            print(f"  ✗ Error converting record: {e}")
            return None
    
    def _parse_timestamp(self, value) -> Optional[int]:
        """
        Parse various timestamp formats to Unix milliseconds.
        
        Handles:
            - ISO 8601 strings: "2025-12-15T10:30:45Z"
            - Unix seconds (int): 1753176645
            - Unix milliseconds (int): 1753176645000
        """
        if value is None:
            return None
        
        # If it's already an int, assume it's Unix seconds or milliseconds
        if isinstance(value, int):
            # If > year 2400 in seconds, assume milliseconds
            if value > 13569465600:  # Jan 1, 2400 in seconds
                return value
            else:
                return value * 1000
        
        if isinstance(value, float):
            # Assume milliseconds if decimal is present
            return int(value * 1000) if value < 10000000000 else int(value)
        
        # Try parsing as ISO 8601 string
        if isinstance(value, str):
            try:
                # Remove 'Z' suffix if present
                value_clean = value.rstrip('Z')
                dt = datetime.fromisoformat(value_clean)
                return int(dt.timestamp() * 1000)
            except ValueError:
                pass
        
        return None
    
    def save_json(self, filepath: str) -> bool:
        """Save exported memories to JSON file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Saved {len(self.memories)} memories to: {filepath}")
            return True
        
        except Exception as e:
            print(f"✗ Failed to save JSON: {e}")
            return False
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            print("✓ Neo4j connection closed")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Export Neo4j memories to Sovereign format")
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON file (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--uri",
        type=str,
        default=NEO4J_URI,
        help=f"Neo4j URI (default: {NEO4J_URI})"
    )
    parser.add_argument(
        "--user",
        type=str,
        default=NEO4J_USER,
        help=f"Neo4j username (default: {NEO4J_USER})"
    )
    parser.add_argument(
        "--password",
        type=str,
        default=NEO4J_PASSWORD,
        help="Neo4j password (default: 'password')"
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print memories to console instead of saving"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🌳 Neo4j → Sovereign Memory Exporter")
    print("=" * 60)
    
    exporter = Neo4jExporter(args.uri, args.user, args.password)
    
    # Connect
    if not exporter.connect():
        sys.exit(1)
    
    # Export
    print("\n📥 Exporting memories...")
    memories = exporter.export_memories()
    
    if not memories:
        print("⚠ No memories found in Neo4j")
        exporter.close()
        return
    
    print(f"\n✓ Exported {len(memories)} memories")
    
    # Display summary
    print("\n📊 Memory Summary:")
    print(f"  Total: {len(memories)}")
    
    roles = {}
    for mem in memories:
        role = mem.get("role", "unknown")
        roles[role] = roles.get(role, 0) + 1
    
    for role, count in sorted(roles.items()):
        print(f"  - {role}: {count}")
    
    # Save or print
    if args.print:
        print("\n📋 Full export (JSON):")
        print(json.dumps(memories, indent=2))
    else:
        if exporter.save_json(args.output):
            print(f"\n✓ Ready to ingest! Drag {args.output} into Sovereign Memory Builder")
        else:
            sys.exit(1)
    
    exporter.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)
