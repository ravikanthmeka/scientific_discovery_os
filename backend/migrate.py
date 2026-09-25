import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("DATABASE_URL not set")
    sys.exit(1)

engine = create_engine(db_url)
with engine.connect() as conn:
    queries = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR DEFAULT 'FREE'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_item_id VARCHAR"
    ]
    for q in queries:
        try:
            conn.execute(text(q))
            conn.commit()
            print(f"Executed: {q}")
        except Exception as e:
            print(f"Error on {q}: {e}")
