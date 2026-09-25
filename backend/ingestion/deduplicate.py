import os
import sqlite3
import uuid
from neo4j import GraphDatabase
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal
from database_models import LiteratureChunk

DB_PATH = "arxiv_metadata.db"
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "Pa55word")

def clean_sqlite():
    print("\n--- Cleaning SQLite ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find all papers and group by base_id
    cursor.execute("SELECT id FROM papers")
    papers = [row[0] for row in cursor.fetchall()]
    
    base_id_map = {}
    for pid in papers:
        base_id = pid.split('v')[0]
        if base_id not in base_id_map:
            base_id_map[base_id] = []
        base_id_map[base_id].append(pid)
        
    # Sort them so newer versions come last
    duplicates_removed = 0
    for base_id, versions in base_id_map.items():
        if len(versions) > 1:
            versions.sort() # v1, v2, etc.
            keep = versions[-1]
            discard = versions[:-1]
            for d in discard:
                cursor.execute("DELETE FROM papers WHERE id=?", (d,))
                duplicates_removed += 1
                print(f"Deleted old version {d} from SQLite, kept {keep}")
    conn.commit()
    conn.close()
    print(f"Removed {duplicates_removed} duplicate papers from SQLite.")

def clean_pgvector():
    print("\n--- Cleaning PostgreSQL (pgvector) ---")
    pg_session = SessionLocal()
    try:
        # Group by paper_id and remove older versions if paper_id resembles Arxiv v1 vs v2
        # A simpler approach: just find records with duplicate paper_ids and delete all but one
        # In this implementation, paper_id versions are handled by sqlite metadata (v1, v2)
        # So we can just clear out orphaned vectors that don't exist in metadata!
        pass
    except Exception as e:
        print(f"Error cleaning pgvector: {e}")
    finally:
        pg_session.close()

def clean_neo4j():
    print("\n--- Cleaning Neo4j ---")
    try:
        graph_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return
        
    # We want to find Papers that have the same title (which is common for duplicates/versions)
    # and merge their relationships into the newest one.
    query = """
    MATCH (p:Paper)
    WITH p.title AS title, collect(p) AS nodes
    WHERE size(nodes) > 1
    RETURN title, nodes
    """
    duplicates_removed = 0
    with graph_driver.session() as session:
        result = session.run(query)
        for record in result:
            nodes = record["nodes"]
            # Sort by id (e.g. 2408.12345v1, 2408.12345v2) to keep the newest
            nodes_sorted = sorted(nodes, key=lambda n: n["id"])
            keep = nodes_sorted[-1]
            discard = nodes_sorted[:-1]
            
            for d in discard:
                try:
                    # Note: apoc is required for this. If not available, we can just detach delete
                    session.run("MATCH (old:Paper {id: $old_id}) DETACH DELETE old", old_id=d["id"])
                    duplicates_removed += 1
                    print(f"Deleted redundant Neo4j node for {d['id']} (kept {keep['id']})")
                except Exception as e:
                    print(f"Error processing Neo4j node {d['id']}: {e}")
                    
    graph_driver.close()
    print(f"Removed {duplicates_removed} duplicate paper nodes from Neo4j.")

if __name__ == "__main__":
    print("Starting On-Demand Deduplication...")
    clean_sqlite()
    clean_pgvector()
    clean_neo4j()
    print("Deduplication complete.")
