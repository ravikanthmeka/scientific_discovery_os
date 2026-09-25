import os
from neo4j import GraphDatabase
from qdrant_client import QdrantClient

print("Checking Qdrant...")
qclient = QdrantClient(path=os.path.abspath(os.path.join(os.path.dirname(__file__), "ingestion", "qdrant_data")))
print([m for m in dir(qclient) if not m.startswith('_')])

print("\nChecking Neo4j...")
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "Pa55word")
driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    print("Node types:")
    result = session.run("MATCH (n) RETURN DISTINCT labels(n) AS labels, count(n) AS count")
    for r in result:
        print(r)
        
    print("\nRelationship types:")
    result = session.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS type, count(r) AS count")
    for r in result:
        print(r)
        
    print("\nTesting simple claims query:")
    result = session.run("MATCH (s:ScientificEntity)-[rel:RELATES_TO]->(o:ScientificEntity) RETURN rel LIMIT 1")
    for r in result:
        print(r)
