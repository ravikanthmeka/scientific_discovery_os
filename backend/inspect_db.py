import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "ingestion", "arxiv_metadata.db")
print("DB Path:", db_path)
conn = sqlite3.connect(db_path)
print("Tables:", conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
try:
    print("Papers schema:", conn.execute("PRAGMA table_info(papers)").fetchall())
    print("Categories:", conn.execute("SELECT category, count(*) FROM papers GROUP BY category").fetchall())
except Exception as e:
    print(e)
