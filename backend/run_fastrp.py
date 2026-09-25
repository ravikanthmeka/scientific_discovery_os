import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "Pa55word")

def run_fastrp():
    print(f"Connecting to Neo4j at {URI}...")
    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        
        with driver.session() as session:
            # 1. Check if GDS is installed
            print("Checking for Neo4j Graph Data Science (GDS) library...")
            try:
                gds_version = session.run("CALL gds.version() YIELD version RETURN version").single()
                if gds_version:
                    print(f"GDS Version found: {gds_version['version']}")
                else:
                    print("GDS library not found. FastRP requires GDS to be installed on your Neo4j server.")
                    return
            except Exception as e:
                print("Failed to call GDS. Ensure the Graph Data Science plugin is installed and enabled.")
                print(e)
                return

            # 2. Project the graph into memory
            graph_name = 'scientific_knowledge_graph'
            print(f"Projecting graph '{graph_name}' into memory...")
            
            # Drop it first if it already exists from a previous run
            session.run(f"CALL gds.graph.drop('{graph_name}', false)")
            
            project_query = """
            CALL gds.graph.project(
              $graph_name,
              ['Domain', 'Methodology'],
              {
                USES: {orientation: 'UNDIRECTED'},
                COULD_APPLY_TO: {orientation: 'UNDIRECTED'}
              }
            )
            """
            session.run(project_query, graph_name=graph_name)
            
            # 3. Run FastRP and write the embeddings to the database nodes
            print("Running FastRP algorithm to generate embeddings...")
            fastrp_query = """
            CALL gds.fastRP.write(
              $graph_name,
              {
                embeddingDimension: 64,
                randomSeed: 42,
                writeProperty: 'fastrp_embedding'
              }
            )
            YIELD nodePropertiesWritten, computeMillis
            RETURN nodePropertiesWritten, computeMillis
            """
            result = session.run(fastrp_query, graph_name=graph_name).single()
            print(f"Successfully wrote embeddings to {result['nodePropertiesWritten']} nodes in {result['computeMillis']} ms.")
            
            # 4. Clean up the projected in-memory graph
            print("Cleaning up in-memory graph...")
            session.run(f"CALL gds.graph.drop('{graph_name}')")
            
            print("FastRP embedding generation complete! You can now use 'fastrp_embedding' for similarity search or ML downstream tasks.")
            
    except Exception as e:
        print(f"Error executing FastRP: {e}")
    finally:
        if 'driver' in locals():
            driver.close()

if __name__ == "__main__":
    run_fastrp()
