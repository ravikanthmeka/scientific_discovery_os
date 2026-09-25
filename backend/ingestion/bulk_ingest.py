import os
import time
import arxiv
import sqlite3
import uuid
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import declarative_base, sessionmaker

# Import pipeline components
from arxiv_pipeline import (
    embed_text, download_source, parse_latex, cleanup_source,
    graph_driver, Session as PipelineSession, PaperMetadata
)
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal
from database_models import LiteratureChunk

from agentic_ingest import agent_parse_latex, agent_extract_entities, agent_extract_claims

# --- Ingestion Tracking Setup ---
Base = declarative_base()
engine = create_engine('sqlite:///ingestion_state.db')
Session = sessionmaker(bind=engine)

class IngestionState(Base):
    __tablename__ = 'ingestion_state'
    query = Column(String, primary_key=True)
    offset = Column(Integer, default=0)

Base.metadata.create_all(engine)

QUERIES = [
    'cat:cs',       # Computer Science
    'cat:q-bio',    # Quantitative Biology
    'cat:q-fin',    # Quantitative Finance
    'cat:stat',     # Statistics
    'cat:eess',     # Electrical Engineering and Systems Science
    'cat:econ'      # Economics
]
BATCH_SIZE = 5
MAX_PAPERS_PER_QUERY = 20  # Limit to 20 for proof-of-concept run

def get_offset(query):
    session = Session()
    state = session.query(IngestionState).filter_by(query=query).first()
    if not state:
        state = IngestionState(query=query, offset=0)
        session.add(state)
        session.commit()
    return state.offset

def update_offset(query, new_offset):
    session = Session()
    state = session.query(IngestionState).filter_by(query=query).first()
    state.offset = new_offset
    session.commit()

def process_paper(paper, query):
    paper_id = paper.get_short_id()
    base_id = paper_id.split('v')[0]
    print(f"\n[{query}] Processing {paper_id}: {paper.title}")
    
    pipeline_session = PipelineSession()
    
    # 1. Metadata -> SQLite
    db_paper = pipeline_session.query(PaperMetadata).filter(PaperMetadata.id.like(f"{base_id}%")).first()
    if db_paper:
        print(f"Paper {base_id} already ingested as {db_paper.id}. Skipping.")
        pipeline_session.close()
        return
        
    new_paper = PaperMetadata(
        id=paper_id,
        title=paper.title,
        authors=", ".join([a.name for a in paper.authors]),
        summary=paper.summary,
        category=query # store query as category for tracking
    )
    pipeline_session.add(new_paper)
    pipeline_session.commit()

    # 2. Abstract -> PostgreSQL
    print("Embedding abstract...")
    try:
        abs_vector = embed_text(paper.summary)
        pg_session = SessionLocal()
        import uuid, json
        abs_chunk = LiteratureChunk(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, paper_id)),
            paper_id=paper_id,
            title=paper.title,
            text=paper.summary,
            embedding=abs_vector,
            metadata_json=json.dumps({"type": "abstract", "query": query})
        )
        pg_session.add(abs_chunk)
        pg_session.commit()
        pg_session.close()
    except Exception as e:
        print(f"Error embedding abstract: {e}")

    # 3. Source -> LaTeX -> Sections -> Agent Processing -> Qdrant
    tar_path = download_source(paper)
    time.sleep(3)
    sections = parse_latex(tar_path)
    print(f"Found {len(sections)} raw chunks. Processing through Agent Pipeline...")
    
    all_entities = []
    all_claims = []
    
    for idx, section_text in enumerate(sections):
        if len(section_text) < 150: continue # Skip trivial chunks
        
        try:
            print(f"  Agent 1: Cleaning LaTeX chunk {idx}...")
            parsed = agent_parse_latex(section_text[:3000]) # limit input tokens
            clean_text = parsed.clean_text
            
            print(f"  Agent 2 & 3: Extracting Entities and Claims from chunk {idx}...")
            entities_obj = agent_extract_entities(clean_text)
            all_entities.extend(entities_obj.entities)
            
            claims_obj = agent_extract_claims(clean_text)
            all_claims.extend(claims_obj.claims)
        except Exception as e:
            print(f"Error in Agent Pipeline for chunk {idx}: {e}")

    # 4. Filter sections and store in PostgreSQL
    print(f"Parsed {len(sections)} sections.")
    
    pg_session = SessionLocal()
    for idx, section_text in enumerate(sections):
        if len(section_text) < 100: continue
        sec_vector = embed_text(section_text)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{paper_id}_{idx}"))
        
        sec_chunk = LiteratureChunk(
            id=point_id,
            paper_id=paper_id,
            title=paper.title,
            text=section_text,
            embedding=sec_vector,
            metadata_json=json.dumps({
                "type": "section",
                "section_idx": idx,
                "content": section_text[:500]
            })
        )
        pg_session.add(sec_chunk)
    
    try:
        pg_session.commit()
    except Exception as e:
        print(f"Error saving to pgvector: {e}")
        pg_session.rollback()
    finally:
        pg_session.close()

    # 4. Agent 4: Relationships & Linker -> Neo4j
    print(f"Storing {len(all_entities)} entities and {len(all_claims)} claims in Neo4j...")
    try:
        with graph_driver.session() as session:
            session.run("""
                MERGE (p:Paper {id: $id, title: $title})
                MERGE (d:Domain {name: $domain})
                MERGE (p)-[:BELONGS_TO]->(d)
            """, id=paper_id, title=paper.title, domain=query.replace('all:', '').replace('"', ''))
            
            for author in paper.authors:
                session.run("""
                    MERGE (a:Author {name: $author_name})
                    WITH a
                    MATCH (p:Paper {id: $paper_id})
                    MERGE (a)-[:WROTE]->(p)
                """, author_name=author.name, paper_id=paper_id)
                
            # Insert Entities
            for ent in all_entities:
                session.run("""
                    MERGE (e:ScientificEntity {name: $name})
                    ON CREATE SET e.type = $type
                    WITH e
                    MATCH (p:Paper {id: $paper_id})
                    MERGE (p)-[:MENTIONS]->(e)
                """, name=ent.name.upper(), type=ent.type, paper_id=paper_id)
                
            # Insert Claims
            for claim in all_claims:
                session.run("""
                    MERGE (s:ScientificEntity {name: $subj})
                    MERGE (o:ScientificEntity {name: $obj})
                    WITH s, o
                    MATCH (p:Paper {id: $paper_id})
                    MERGE (s)-[rel:RELATES_TO {predicate: $pred}]->(o)
                    SET rel.evidence = $evid
                    MERGE (p)-[:MENTIONS]->(s)
                    MERGE (p)-[:MENTIONS]->(o)
                """, subj=claim.subject.upper(), obj=claim.object.upper(), 
                     pred=claim.predicate, evid=claim.evidence_level, paper_id=paper_id)
                     
    except Exception as e:
        print(f"Neo4j Agent Error: {e}")

    # 5. Cleanup
    print("Cleaning up source files...")
    cleanup_source(paper_id)

def run_bulk_ingest(max_papers=None):
    client = arxiv.Client(
        page_size=BATCH_SIZE,
        delay_seconds=3,
        num_retries=3
    )

    for query in QUERIES:
        offset = get_offset(query)
        print(f"\n{'='*50}\nStarting Query: {query} (Offset: {offset})\n{'='*50}")
        
        limit = max_papers if max_papers else MAX_PAPERS_PER_QUERY
        
        if offset >= limit:
            print(f"Already reached target for {query}")
            continue

        search = arxiv.Search(
            query=query,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        # arxiv library's client.results() generator
        results_generator = client.results(search)
        
        # Fast forward generator to offset
        # Note: arxiv client handles pagination internally, but to resume 
        # we have to burn through the generator if it doesn't support offset directly.
        # Alternatively, we could use arxiv Search offset, but it's deprecated in some versions.
        # The arxiv.Search doesn't have an offset parameter directly exposed in the 2.x API.
        
        processed_in_this_run = 0
        papers_iter = iter(results_generator)
        
        # Fast-forwarding
        if offset > 0:
            print(f"Fast-forwarding past {offset} papers...")
            for _ in range(offset):
                try:
                    next(papers_iter)
                except StopIteration:
                    break

        # Process next batch
        try:
            for paper in papers_iter:
                if offset >= limit:
                    break
                    
                process_paper(paper, query)
                
                offset += 1
                update_offset(query, offset)
                processed_in_this_run += 1
                
                # Small sleep to be safe, even though client handles some
                time.sleep(1)
                
        except Exception as e:
            print(f"Error during bulk fetch loop: {e}")
            print(f"Saved offset {offset}. Can resume later.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bulk Ingest arXiv Papers")
    parser.add_argument("--test-run", action="store_true", help="Only process 5 papers per query")
    parser.add_argument("--max-papers", type=int, default=None, help="Max papers to fetch per query")
    args = parser.parse_args()
    
    limit = 5 if args.test_run else args.max_papers
    run_bulk_ingest(max_papers=limit)
