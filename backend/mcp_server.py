import os
import sys
import hashlib
import json
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import database
import database_models

# Initialize connections lazily to prevent MCP initialization timeouts
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "Pa55word")

import sys

graph_driver = None
embedder = None
_initialized = False

def initialize_resources():
    global graph_driver, embedder, _initialized
    if _initialized:
        return
        
    try:
        graph_driver = GraphDatabase.driver(uri, auth=(user, password))
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}", file=sys.stderr)

    try:
        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        print(f"Failed to initialize sentence transformer: {e}", file=sys.stderr)
        
    _initialized = True

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

app = Server("ScientificDiscoveryDataLayer")

def do_search_literature(query: str, n_results: int = 3) -> list[dict]:
    initialize_resources()
    if not embedder:
        return []
    vector = embedder.encode(query).tolist()
    
    db = next(database.get_db())
    try:
        # Use cosine distance <=> for pgvector sorting
        chunks = db.query(database_models.LiteratureChunk).order_by(
            database_models.LiteratureChunk.embedding.cosine_distance(vector)
        ).limit(n_results).all()
        
        pruned_results = []
        for chunk in chunks:
            payload = {}
            if chunk.metadata_json:
                import json
                try:
                    payload = json.loads(chunk.metadata_json)
                except:
                    pass
            text = chunk.text or ""
            if len(text) > 500:
                text = text[:500] + "..."
            payload["text"] = text
            payload["paper_id"] = chunk.paper_id
            payload["title"] = chunk.title
            pruned_results.append(payload)
            
        return pruned_results
    except Exception as e:
        print(f"Error searching pgvector: {e}", file=sys.stderr)
        return []
    finally:
        db.close()

def do_get_domain_methodologies(domain: str) -> list[str]:
    initialize_resources()
    if not graph_driver:
        return []
    query = """
    MATCH (d:Domain)-[:USES]->(m:Methodology)
    WHERE toLower(d.name) CONTAINS toLower($domain) OR toLower($domain) CONTAINS toLower(d.name)
    RETURN m.name AS method
    """
    try:
        with graph_driver.session() as session:
            result = session.run(query, domain=domain)
            methods = [record["method"] for record in result]
            if not methods:
                fallback_query = """
                MATCH (m:Methodology)
                RETURN m.name AS method
                LIMIT 20
                """
                result = session.run(fallback_query)
                methods = [record["method"] for record in result]
            return methods
    except Exception as e:
        print(f"Error querying Neo4j: {e}", file=sys.stderr)
        return []

def do_find_analogous_domains(domain: str) -> list[dict]:
    initialize_resources()
    if not graph_driver:
        return []
    query = """
    MATCH (d1:Domain)<-[:BELONGS_TO]-(p1:Paper)-[:MENTIONS]->(e:ScientificEntity)<-[:MENTIONS]-(p2:Paper)-[:BELONGS_TO]->(d2:Domain)
    WHERE toLower(d1.name) CONTAINS toLower($domain) AND d1 <> d2
    RETURN DISTINCT d2.name AS analogous_domain, count(e) AS shared_entities
    ORDER BY shared_entities DESC
    LIMIT 5
    """
    try:
        with graph_driver.session() as session:
            result = session.run(query, domain=domain)
            return [{"domain": record["analogous_domain"], "shared_entities": record["shared_entities"]} for record in result]
    except Exception as e:
        print(f"Error querying Neo4j for analogous domains: {e}", file=sys.stderr)
        return []

import requests
def do_search_openalex(query: str, n_results: int = 5) -> list[dict]:
    try:
        query_key = f"{query.strip().lower()}::limit_{n_results}"
        query_hash = hashlib.md5(query_key.encode('utf-8')).hexdigest()

        # Check Cache
        db = database.SessionLocal()
        try:
            cached = db.query(database_models.OpenAlexCache).filter(database_models.OpenAlexCache.query_hash == query_hash).first()
            if cached:
                print(f"OpenAlex Cache Hit for query: {query_key}", file=sys.stderr)
                return json.loads(cached.results)
        finally:
            db.close()

        print(f"OpenAlex Cache Miss for query: {query_key}. Fetching...", file=sys.stderr)
        url = f"https://api.openalex.org/works?search={query}&per-page={n_results}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for w in data.get("results", []):
            concepts = [c.get("display_name") for c in w.get("concepts", [])[:5]]
            keywords = [k.get("display_name") for k in w.get("keywords", [])[:5]]
            results.append({
                "id": w.get("id"),
                "title": w.get("title"),
                "publication_year": w.get("publication_year"),
                "cited_by_count": w.get("cited_by_count"),
                "concepts": concepts,
                "keywords": keywords
            })
            
        # Save to Cache
        db = database.SessionLocal()
        try:
            new_cache = database_models.OpenAlexCache(
                query_hash=query_hash,
                query=query_key,
                results=json.dumps(results)
            )
            db.merge(new_cache)
            db.commit()
        except Exception as e:
            print(f"Failed to cache OpenAlex results: {e}", file=sys.stderr)
        finally:
            db.close()

        return results
    except Exception as e:
        print(f"Error querying OpenAlex: {e}", file=sys.stderr)
        return []

@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_literature",
            description="Search the vector database for papers semantically matching the query. Returns a list of text chunks and their associated metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "n_results": {"type": "integer", "default": 3}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_domain_methodologies",
            description="Retrieve scientific methodologies related to the specified domain from the graph database. Returns a list of methodology names.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string"}
                },
                "required": ["domain"]
            }
        ),
        types.Tool(
            name="find_analogous_domains",
            description="Find scientific domains that are analogous to the target domain based on shared scientific entities and methodologies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string"}
                },
                "required": ["domain"]
            }
        ),
        types.Tool(
            name="openalex_search_works",
            description="Search the OpenAlex database for scholarly papers. Returns metadata including title, citations, and related concepts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "n_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "search_literature":
        query = arguments.get("query")
        n_results = arguments.get("n_results", 3)
        res = await asyncio.to_thread(do_search_literature, query, n_results)
        return [types.TextContent(type="text", text=str(res))]
    elif name == "get_domain_methodologies":
        domain = arguments.get("domain")
        res = await asyncio.to_thread(do_get_domain_methodologies, domain)
        return [types.TextContent(type="text", text=str(res))]
    elif name == "find_analogous_domains":
        domain = arguments.get("domain")
        res = await asyncio.to_thread(do_find_analogous_domains, domain)
        return [types.TextContent(type="text", text=str(res))]
    elif name == "openalex_search_works":
        query = arguments.get("query")
        n_results = arguments.get("n_results", 5)
        res = await asyncio.to_thread(do_search_openalex, query, n_results)
        return [types.TextContent(type="text", text=str(res))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
