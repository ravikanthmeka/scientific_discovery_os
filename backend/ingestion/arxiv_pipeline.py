import os
import tarfile
import urllib.request
import ssl
import arxiv

# Bypass SSL certificate verification for local Windows environments
ssl._create_default_https_context = ssl._create_unverified_context
from TexSoup import TexSoup
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, Column, String, Text, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal
from database_models import LiteratureChunk
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# --- Config & Initialization ---
# SQLite Setup
Base = declarative_base()
engine = create_engine('sqlite:///arxiv_metadata.db')
Session = sessionmaker(bind=engine)

class PaperMetadata(Base):
    __tablename__ = 'papers'
    id = Column(String, primary_key=True)
    title = Column(String)
    authors = Column(String)
    summary = Column(Text)
    category = Column(String)

Base.metadata.create_all(engine)

# Qdrant Setup removed - using pgvector

# HuggingFace Embedding Model
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Neo4j Setup
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "Pa55word")
graph_driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

# --- Pipeline Functions ---
def fetch_arxiv_papers(category: str, max_results: int = 5):
    print(f"Fetching top {max_results} papers for category {category}...")
    search = arxiv.Search(
        query=f"cat:{category}",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    client = arxiv.Client()
    return list(client.results(search))

def embed_text(text: str):
    return embedder.encode(text).tolist()

def download_source(paper, download_dir="./downloads"):
    os.makedirs(download_dir, exist_ok=True)
    paper_id = paper.get_short_id()
    safe_paper_id = paper_id.replace('/', '_')
    tar_path = os.path.join(download_dir, f"{safe_paper_id}.tar.gz")
    if not os.path.exists(tar_path):
        print(f"Downloading source for {paper_id}...")
        url = f"https://arxiv.org/e-print/{paper_id}"
        urllib.request.urlretrieve(url, tar_path)
    return tar_path

def parse_latex(tar_path, extract_dir="./extracted"):
    print(f"Parsing LaTeX source {tar_path}...")
    paper_id = os.path.basename(tar_path).replace('.tar.gz', '')
    paper_dir = os.path.join(extract_dir, paper_id)
    
    sections = []
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=paper_dir)
        
        for root, _, files in os.walk(paper_dir):
            for file in files:
                if file.endswith('.tex'):
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        try:
                            soup = TexSoup(content)
                            for section in soup.find_all('section'):
                                sections.append(str(section))
                            # Fallback if no structured sections
                            if not sections:
                                sections.append(content[:1000]) # grab first 1000 chars
                        except Exception as e:
                            print(f"TexSoup failed for {file}, storing raw chunk. Error: {e}")
                            sections.append(content[:1000])
    except Exception as e:
        print(f"Failed to extract or parse {tar_path}: {e}")
    
    return sections

import shutil

def cleanup_source(paper_id, download_dir="./downloads", extract_dir="./extracted"):
    safe_paper_id = paper_id.replace('/', '_')
    tar_path = os.path.join(download_dir, f"{safe_paper_id}.tar.gz")
    paper_dir = os.path.join(extract_dir, safe_paper_id)
    
    if os.path.exists(tar_path):
        try:
            os.remove(tar_path)
            print(f"Cleaned up {tar_path}")
        except Exception as e:
            print(f"Failed to delete {tar_path}: {e}")
            
    if os.path.exists(paper_dir):
        try:
            shutil.rmtree(paper_dir)
            print(f"Cleaned up {paper_dir}")
        except Exception as e:
            print(f"Failed to delete {paper_dir}: {e}")

def store_in_neo4j(paper):
    with graph_driver.session() as session:
        # Create Paper
        session.run("""
            MERGE (p:Paper {id: $id, title: $title})
            MERGE (d:Domain {name: 'Quantum Physics'})
            MERGE (p)-[:BELONGS_TO]->(d)
        """, id=paper.get_short_id(), title=paper.title)
        
        # Link Authors
        for author in paper.authors:
            session.run("""
                MERGE (a:Author {name: $author_name})
                WITH a
                MATCH (p:Paper {id: $paper_id})
                MERGE (a)-[:WROTE]->(p)
            """, author_name=author.name, paper_id=paper.get_short_id())

def run_pipeline(category="quant-ph", max_results=2):
    papers = fetch_arxiv_papers(category, max_results)
    session = Session()
    
    for paper in papers:
        paper_id = paper.get_short_id()
        print(f"\nProcessing {paper_id}: {paper.title}")
        
        # 1. Metadata -> SQLite
        db_paper = session.query(PaperMetadata).filter_by(id=paper_id).first()
        if not db_paper:
            new_paper = PaperMetadata(
                id=paper_id,
                title=paper.title,
                authors=", ".join([a.name for a in paper.authors]),
                summary=paper.summary,
                category=category
            )
            session.add(new_paper)
            session.commit()
        
        # 2. Abstract -> PostgreSQL (pgvector)
        print("Embedding abstract...")
        abs_vector = embed_text(paper.summary)
        
        pg_session = SessionLocal()
        import uuid, json
        
        abs_chunk = LiteratureChunk(
            id=str(uuid.uuid4()),
            paper_id=paper_id,
            title=paper.title,
            text=paper.summary,
            embedding=abs_vector,
            metadata_json=json.dumps({"type": "abstract"})
        )
        pg_session.add(abs_chunk)
        
        # 3. Source -> LaTeX -> Sections -> PostgreSQL (pgvector)
        tar_path = download_source(paper)
        sections = parse_latex(tar_path)
        print(f"Found {len(sections)} sections/chunks.")
        
        for idx, section_text in enumerate(sections):
            if len(section_text) < 50: continue # skip very short sections
            sec_vector = embed_text(section_text)
            sec_chunk = LiteratureChunk(
                id=str(uuid.uuid4()),
                paper_id=paper_id,
                title=paper.title,
                text=section_text,
                embedding=sec_vector,
                metadata_json=json.dumps({"type": "section", "section_idx": idx})
            )
            pg_session.add(sec_chunk)
            
        try:
            pg_session.commit()
        except Exception as e:
            print(f"Error saving to pgvector: {e}")
            pg_session.rollback()
        finally:
            pg_session.close()
        # 4. Relationships -> Neo4j
        print("Storing structural graph in Neo4j...")
        store_in_neo4j(paper)

    print("\nPipeline execution complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run arXiv Ingestion Pipeline")
    parser.add_argument("--category", type=str, default="quant-ph", help="arXiv category to fetch")
    parser.add_argument("--max", type=int, default=2, help="Max results to fetch")
    args = parser.parse_args()
    
    run_pipeline(category=args.category, max_results=args.max)
