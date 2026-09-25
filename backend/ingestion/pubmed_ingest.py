import os
import time
import uuid
import requests
import xml.etree.ElementTree as ET

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
engine = create_engine('sqlite:///pubmed_ingestion_state.db')
Session = sessionmaker(bind=engine)

class PubmedIngestionState(Base):
    __tablename__ = 'pubmed_ingestion_state'
    query = Column(String, primary_key=True)
    offset = Column(Integer, default=0)

Base.metadata.create_all(engine)

QUERIES = [
    'biology[MeSH Terms]',
    'healthcare[MeSH Terms]',
    'materials science[MeSH Terms]',
    'quantum computing[MeSH Terms]',
    'genetics[MeSH Terms]'
]
BATCH_SIZE = 5
MAX_PAPERS_PER_QUERY = 10  # Limit for proof-of-concept run

def get_offset(query):
    session = Session()
    state = session.query(PubmedIngestionState).filter_by(query=query).first()
    if not state:
        state = PubmedIngestionState(query=query, offset=0)
        session.add(state)
        session.commit()
    return state.offset

def update_offset(query, new_offset):
    session = Session()
    state = session.query(PubmedIngestionState).filter_by(query=query).first()
    state.offset = new_offset
    session.commit()

def process_pubmed_paper(pmid, title, authors, abstract, query):
    paper_id = f"PMID:{pmid}"
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
    print("Embedding abstract...")
    try:
        abs_vector = embed_text(abstract)
        pg_session = SessionLocal()
        import json
        abs_chunk = LiteratureChunk(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, paper_id)),
            paper_id=paper_id,
            title=title,
            text=abstract,
            embedding=abs_vector,
            metadata_json=json.dumps({"type": "abstract", "query": query})
        )
        pg_session.add(abs_chunk)
        pg_session.commit()
        pg_session.close()
    except Exception as e:
        print(f"Error embedding abstract: {e}")

    # 3. Agent Processing -> Qdrant & Neo4j
    print(f"Running Agent Pipeline on Abstract...")
    
    all_entities = []
    all_claims = []
    
    try:
        # Since we only have the abstract, we skip parse_latex and run extraction directly
        print(f"  Agent 2 & 3: Extracting Entities and Claims from Abstract...")
        entities_obj = agent_extract_entities(abstract)
        all_entities.extend(entities_obj.entities)
        
        claims_obj = agent_extract_claims(abstract)
        all_claims.extend(claims_obj.claims)
        
        # Also save abstract as a section since PubMed often lacks full text
        print("Embedding abstract as section...")
        sec_vector = embed_text(abstract)
        import json
        pg_session = SessionLocal()
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
        print(f"Error in Agent Pipeline: {e}")

    # 4. Agent 4: Relationships & Linker -> Neo4j
    print(f"Storing {len(all_entities)} entities and {len(all_claims)} claims in Neo4j...")
    try:
        with graph_driver.session() as session:
            session.run("""
                MERGE (p:Paper {id: $id, title: $title})
                MERGE (d:Domain {name: $domain})
                MERGE (p)-[:BELONGS_TO]->(d)
            """, id=paper_id, title=title, domain=query.replace('[MeSH Terms]', ''))
            
            for author in authors:
                session.run("""
                    MERGE (a:Author {name: $author_name})
                    WITH a
                    MATCH (p:Paper {id: $paper_id})
                    MERGE (a)-[:WROTE]->(p)
                """, author_name=author, paper_id=paper_id)
                
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

def run_pubmed_ingest(max_papers=None):
    for query in QUERIES:
        offset = get_offset(query)
        print(f"\n{'='*50}\nStarting Query: {query} (Offset: {offset})\n{'='*50}")
        
        limit = max_papers if max_papers else MAX_PAPERS_PER_QUERY
        processed_count = 0
        
        while processed_count < limit:
            batch_fetch = min(BATCH_SIZE, limit - processed_count)
            
            # 1. Search for PMIDs
            search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmode=json&retmax={batch_fetch}&retstart={offset}"
            try:
                resp = requests.get(search_url).json()
                pmids = resp.get("esearchresult", {}).get("idlist", [])
            except Exception as e:
                print(f"Search API Error: {e}")
                break
                
            if not pmids:
                print("No more PMIDs found for query.")
                break
                
            time.sleep(0.35) # Rate limit to ~3/sec
            
            # 2. Fetch XML
            pmids_str = ",".join(pmids)
            fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmids_str}&retmode=xml"
            try:
                xml_resp = requests.get(fetch_url).text
                root = ET.fromstring(xml_resp)
            except Exception as e:
                print(f"Fetch API Error: {e}")
                break
                
            time.sleep(0.35) # Rate limit to ~3/sec
            
            for article in root.findall(".//PubmedArticle"):
                try:
                    pmid = article.find(".//PMID").text
                    title = article.find(".//ArticleTitle").text
                    
                    abstract_elem = article.find(".//AbstractText")
                    abstract = abstract_elem.text if abstract_elem is not None else ""
                    if not abstract or len(abstract) < 50:
                        print(f"Skipping PMID {pmid} due to missing/short abstract.")
                        continue
                        
                    authors = []
                    for author in article.findall(".//Author"):
                        last = author.find("LastName")
                        fore = author.find("ForeName")
                        if last is not None and fore is not None:
                            authors.append(f"{fore.text} {last.text}")
                            
                    process_pubmed_paper(pmid, title, authors, abstract, query)
                    processed_count += 1
                except Exception as e:
                    print(f"Error processing XML for article: {e}")
                    
                if processed_count >= limit:
                    break
                    
            offset += len(pmids)
            update_offset(query, offset)

if __name__ == "__main__":
    run_pubmed_ingest(max_papers=6)
