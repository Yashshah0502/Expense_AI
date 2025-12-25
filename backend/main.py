from fastapi import FastAPI, Query
from dotenv import load_dotenv
import psycopg
import os

from rag.policy_search import hybrid_search

load_dotenv()
app = FastAPI()

DB_URL = os.getenv("DATABASE_URL")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db-health")
def db_health():
    if not DB_URL:
        return {"status": "error", "detail": "DATABASE_URL is missing"}

    # Simple, safe connectivity check
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            val = cur.fetchone()[0]

    return {"status": "ok", "db": val}

@app.get("/policy/search")
def policy_search(q: str = Query(..., min_length=2), top_k: int = 5):
    try:
        return hybrid_search(q, top_k)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

