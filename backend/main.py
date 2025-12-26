from fastapi import FastAPI, Query
from typing import Optional
from dotenv import load_dotenv
import psycopg
import os

from rag.policy_search import hybrid_search
from rag.answer_gen import generate_answer

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
def policy_search(
    q: str = Query(..., min_length=2, description="Search query"),
    org: Optional[str] = Query(None, description="Filter by org/university (e.g., ASU, PRINCETON)"),
    policy_type: Optional[str] = Query(None, description="Filter by type (travel/procurement/general)"),
    doc_name: Optional[str] = Query(None, description="Filter to specific PDF filename"),
    candidate_k: int = Query(30, description="Number of candidates to retrieve"),
    final_k: int = Query(5, alias="top_k", description="Number of final results"),
    debug: bool = Query(False, description="Include debug information"),
):
    """
    Search policy documents with optional filters.
    Returns ranked chunks with metadata.
    """
    try:
        filters = {}
        if org:
            filters["org"] = org.upper()
        if policy_type:
            filters["policy_type"] = policy_type.lower()
        if doc_name:
            filters["doc_name"] = doc_name
            
        return hybrid_search(
            q=q,
            top_k=final_k,
            candidate_k=candidate_k,
            filters=filters,
            debug=debug,
        )
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/policy/answer")
def policy_answer(
    q: str = Query(..., min_length=2, description="Question to answer"),
    org: Optional[str] = Query(None, description="Filter by org/university"),
    policy_type: Optional[str] = Query(None, description="Filter by type"),
    doc_name: Optional[str] = Query(None, description="Filter to specific PDF"),
    candidate_k: int = Query(30, description="Number of candidates to retrieve"),
    final_k: int = Query(5, description="Number of sources to use for answer"),
):
    """
    Answer a policy question using retrieval + LLM generation.
    Returns an answer with citations.
    """
    try:
        filters = {}
        if org:
            filters["org"] = org.upper()
        if policy_type:
            filters["policy_type"] = policy_type.lower()
        if doc_name:
            filters["doc_name"] = doc_name
            
        return generate_answer(
            query=q,
            filters=filters,
            candidate_k=candidate_k,
            final_k=final_k,
        )
    except Exception as e:
        return {"status": "error", "detail": str(e)}
