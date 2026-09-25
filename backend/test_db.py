from database import vector_db, graph_db

print("Testing Vector DB...")
results = vector_db.search_similar_papers("quantum error correction", n_results=5)
print(f"Vector results: {len(results)}")
for r in results:
    print(r)

print("\nTesting Graph DB...")
claims = graph_db.get_related_methodologies("Quantum")
print(f"Graph claims: {len(claims)}")
for c in claims:
    print(c)
