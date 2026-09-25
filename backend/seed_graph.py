import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "Pa55word")

def seed_database():
    print(f"Connecting to Neo4j at {URI}...")
    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        
        with driver.session() as session:
            print("Clearing existing data...")
            session.run("MATCH (n) DETACH DELETE n")
            
            print("Seeding domain knowledge...")
            
            # Nuclear Domain
            session.run("""
                MERGE (d:Domain {name: 'Nuclear'})
                MERGE (m1:Methodology {name: 'Monte Carlo Particle Transport'})
                MERGE (m2:Methodology {name: 'Magnetic Confinement Synthesis'})
                MERGE (d)-[:USES]->(m1)
                MERGE (d)-[:USES]->(m2)
            """)
            
            # Biology Domain
            session.run("""
                MERGE (d:Domain {name: 'Biology'})
                MERGE (m1:Methodology {name: 'CRISPR-Cas9 Editing'})
                MERGE (m2:Methodology {name: 'Protein Folding Simulation'})
                MERGE (d)-[:USES]->(m1)
                MERGE (d)-[:USES]->(m2)
            """)
            
            # Materials Domain
            session.run("""
                MERGE (d:Domain {name: 'Materials'})
                MERGE (m1:Methodology {name: 'Density Functional Theory (DFT)'})
                MERGE (m2:Methodology {name: 'X-Ray Crystallography'})
                MERGE (d)-[:USES]->(m1)
                MERGE (d)-[:USES]->(m2)
            """)
            
            # Cross-domain relationships (The real power of Graph-RAG)
            session.run("""
                MATCH (m:Methodology {name: 'Monte Carlo Particle Transport'}), (d:Domain {name: 'Biology'})
                MERGE (m)-[:COULD_APPLY_TO {reason: 'Stochastic protein folding paths'}]->(d)
                
                MATCH (m2:Methodology {name: 'Density Functional Theory (DFT)'}), (d2:Domain {name: 'Biology'})
                MERGE (m2)-[:COULD_APPLY_TO {reason: 'Enzyme active site quantum modeling'}]->(d2)
            """)
            
            print("Database seeded successfully!")
            
    except Exception as e:
        print(f"Error connecting or seeding Neo4j: {e}")
    finally:
        if 'driver' in locals():
            driver.close()

if __name__ == "__main__":
    seed_database()
