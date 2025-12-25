import os
import psycopg
from .embeddings import get_embedding
from .rerank import rerank_documents

# Internal constants for retrieval params
CANDIDATE_K = 30

def keyword_search(cur, q: str, top_k: int):
    """
    Performs full-text keyword search using PostgreSQL tsvector.
    
    Args:
        cur: Database cursor
        q: Query string
        top_k: Number of results to return
        
    Returns:
        List of results from the database
    """
    cur.execute(
        """
        SELECT doc_name, chunk_index, LEFT(content, 400) AS snippet,
               ts_rank(content_tsv, plainto_tsquery('english', %s)) AS score
        FROM policy_chunks
        WHERE content_tsv @@ plainto_tsquery('english', %s)
        ORDER BY score DESC
        LIMIT %s;
        """,
        (q, q, top_k),
    )
    return cur.fetchall()

def vector_search(cur, q_vec: list[float], top_k: int):
    """
    Performs vector similarity search using pgvector.
    
    Args:
        cur: Database cursor
        q_vec: Query embedding vector
        top_k: Number of results to return
        
    Returns:
        List of results from the database
    """
    cur.execute(
        """
        SELECT doc_name, chunk_index, LEFT(content, 400) AS snippet,
               (embedding <=> %s::vector) AS distance
        FROM policy_chunks
        WHERE embedding IS NOT NULL
        ORDER BY distance ASC
        LIMIT %s;
        """,
        (q_vec, top_k),
    )
    return cur.fetchall()

def hybrid_search(q: str, top_k: int = 5):
    """
    Combines keyword, vector search, and reranking to return the best matches.
    
    Args:
        q: Query string
        top_k: Number of final results to return (FINAL_K)
        
    Returns:
        Dictionary containing the query and ranked results
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set")

    # 1) Embed the query
    q_vec = get_embedding(q)

    keyword_rows = []
    vector_rows = []

    # 2) Retrieve Candidates (Retrieve Stage)
    # We fetch CANDIDATE_K items from each source
    retrieve_k = CANDIDATE_K

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            keyword_rows = keyword_search(cur, q, retrieve_k)
            vector_rows = vector_search(cur, q_vec, retrieve_k)

    # 3) Merge + Dedupe
    merged = {}

    # Keyword results
    for doc_name, chunk_index, snippet, score in keyword_rows:
        key = (doc_name, chunk_index)
        merged[key] = {
            "doc_name": doc_name,
            "chunk_index": chunk_index,
            "snippet": snippet,
            "keyword_score": float(score),
            "vector_distance": None,
            "source": "keyword"
        }

    # Vector results
    for doc_name, chunk_index, snippet, dist in vector_rows:
        key = (doc_name, chunk_index)
        if key not in merged:
            merged[key] = {
                "doc_name": doc_name,
                "chunk_index": chunk_index,
                "snippet": snippet,
                "keyword_score": None,
                "vector_distance": float(dist),
                "source": "vector"
            }
        else:
            merged[key]["vector_distance"] = float(dist)
            merged[key]["source"] = "both"

    candidates = list(merged.values())
    
    # Optional logic: if you wanted to pre-sort candidates before reranking to trim list, 
    # you could do it here, but we usually just rerank all unique candidates found.
    
    # 4) Rerank (Rerank Stage)
    # This assigns a "rerank_score" to each candidate and sorts them.
    ranked_results = rerank_documents(q, candidates, top_k=top_k)

    return {"query": q, "results": ranked_results}
