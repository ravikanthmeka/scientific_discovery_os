import os
import time
import uuid
import requests

from arxiv_pipeline import (
    embed_text, graph_driver, Session as PipelineSession, PaperMetadata
)
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal
from database_models import LiteratureChunk
from agentic_ingest import agent_extract_entities, agent_extract_claims

from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Ingestion Tracking Setup ---
Base = declarative_base()
engine = create_engine('sqlite:///openalex_ingestion_state.db')
Session = sessionmaker(bind=engine)

class OpenAlexIngestionState(Base):
    __tablename__ = 'openalex_ingestion_state'
    query = Column(String, primary_key=True)
    page = Column(Integer, default=1)

Base.metadata.create_all(engine)

QUERIES = [
    'biology',
    'healthcare',
    'materials science',
    'quantum computing',
    'genetics'
]
BATCH_SIZE = 5
MAX_PAPERS_PER_QUERY = 5  # Limit for proof-of-concept run

def get_page(query):
    session = Session()
    state = session.query(OpenAlexIngestionState).filter_by(query=query).first()
    if not state:
        state = OpenAlexIngestionState(query=query, page=1)
        session.add(state)
        session.commit()
    return state.page

def update_page(query, new_page):
    session = Session()
    state = session.query(OpenAlexIngestionState).filter_by(query=query).first()
    state.page = new_page
    session.commit()

def process_openalex_paper(work_id, title, authors, abstract, concepts, query):
    paper_id = f"OPENALEX:{work_id.split('/')[-1]}"
    print(f"\n[{query}] Processing {paper_id}: {title}")
    
    pipeline_session = PipelineSession()
    
    # 1. Metadata -> SQLite
    db_paper = pipeline_session.query(PaperMetadata).filter(PaperMetadata.id == paper_id).first()
    if db_paper:
        print(f"Paper {paper_id} already ingested. Skipping.")
        pipeline_session.close()
        return
        
    new_paper = PaperMetadata(
        id=paper_id,
        title=title,
        authors=", ".join(authors),
        summary=abstract,
        category=query
    )
    pipeline_session.add(new_paper)
    pipeline_session.commit()
    pipeline_session.close()

    # 2. Abstract -> PostgreSQL
    all_claims = []
    if abstract:
        try:
            claims_obj = agent_extract_claims(abstract)
            all_claims.extend(claims_obj.claims)
            
            # Embed the abstract as a section
            print("Embedding abstract as section...")
            sec_vector = embed_text(abstract)
            pg_session = SessionLocal()
            import json
            sec_chunk = LiteratureChunk(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{paper_id}_abstract")),
                paper_id=paper_id,
                title=title,
                text=abstract,
                embedding=sec_vector,
                metadata_json=json.dumps({"type": "section", "section_idx": 0, "content": abstract[:500]})
            )
            pg_session.add(sec_chunk)
            pg_session.commit()
            pg_session.close()
            
        except Exception as e:
            print(f"Error extracting claims from abstract: {e}")

    # 3. Agent Processing -> Neo4j
    all_entities = []
    
    # Use OpenAlex native concepts directly! No need to run the LLM extraction!
    # This is the beauty of OpenAlex being a graph database natively.
    for concept in concepts:
        all_entities.append({
            "name": concept.get("display_name"),
            "type": "Concept",
            "score": concept.get("score")
        })
        
    print(f"Extracted {len(all_entities)} native concepts from OpenAlex graph.")

    # 4. Native OpenAlex Relations -> Neo4j
    print(f"Storing {len(all_entities)} concepts in Neo4j...")
    try:
        with graph_driver.session() as session:
            session.run("""
                MERGE (p:Paper {id: $id, title: $title})
                MERGE (d:Domain {name: $domain})
                MERGE (p)-[:BELONGS_TO]->(d)
            """, id=paper_id, title=title, domain=query)
            
            for author in authors:
                session.run("""
                    MERGE (a:Author {name: $author_name})
                    WITH a
                    MATCH (p:Paper {id: $paper_id})
                    MERGE (a)-[:WROTE]->(p)
                """, author_name=author, paper_id=paper_id)
                
            # Insert Native Concepts as Entities
            for ent in all_entities:
                session.run("""
                    MERGE (e:ScientificEntity {name: $name})
                    ON CREATE SET e.type = $type
                    WITH e
                    MATCH (p:Paper {id: $paper_id})
                    MERGE (p)-[:MENTIONS {score: $score}]->(e)
                """, name=ent["name"].upper(), type=ent["type"], score=ent["score"], paper_id=paper_id)
                     
    except Exception as e:
        print(f"Neo4j Agent Error: {e}")

def run_openalex_ingest(max_papers=None):
    for query in QUERIES:
        page = get_page(query)
        print(f"\n{'='*50}\nStarting Query: {query} (Page: {page})\n{'='*50}")
        
        limit = max_papers if max_papers else MAX_PAPERS_PER_QUERY
        processed_count = 0
        
        while processed_count < limit:
            # 1. Search for Works
            search_url = f"https://api.openalex.org/works?search={query}&per-page={BATCH_SIZE}&page={page}"
            try:
                resp = requests.get(search_url).json()
                results = resp.get("results", [])
            except Exception as e:
                print(f"Search API Error: {e}")
                break
                
            if not results:
                print("No more works found for query.")
                break
                
            for work in results:
                try:
                    work_id = work.get("id")
                    title = work.get("title")
                    if not title: continue
                    
                    # Construct authors
                    authors = []
                    for authorship in work.get("authorships", []):
                        author_info = authorship.get("author", {})
                        if "display_name" in author_info:
                            authors.append(author_info["display_name"])
                            
                    # Construct Abstract from inverted index
                    abstract = ""
                    inverted = work.get("abstract_inverted_index")
                    if inverted:
                        # Find max index
                        max_idx = max([idx for indices in inverted.values() for idx in indices])
                        words = [""] * (max_idx + 1)
                        for word, indices in inverted.items():
                            for idx in indices:
                                words[idx] = word
                        abstract = " ".join(words)
                    
                    concepts = work.get("concepts", [])
                        
                    process_openalex_paper(work_id, title, authors, abstract, concepts, query)
                    processed_count += 1
                except Exception as e:
                    print(f"Error processing work: {e}")
                    
                if processed_count >= limit:
                    break
                    
            page += 1
            update_page(query, page)
            time.sleep(1) # Polite limit

if __name__ == "__main__":
    run_openalex_ingest(max_papers=5)
