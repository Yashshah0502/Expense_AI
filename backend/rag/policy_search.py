import os
import psycopg
from .embeddings import get_embedding
from .rerank import rerank_documents

# Internal constants for retrieval params
CANDIDATE_K = 30

def build_filter_clauses(filters: dict):
    """
    Build SQL WHERE clauses and parameters for filtering.

    Args:
        filters: Dictionary with optional keys: org, orgs, policy_type, doc_name

    Returns:
        Tuple of (SQL clause string, parameters dict)
    """
    clauses = []
    params = {}

    # Handle single org or multiple orgs (mutually exclusive)
    if filters.get("org"):
        clauses.append("org = %(org)s")
        params["org"] = filters["org"]
    elif filters.get("orgs"):
        # Use PostgreSQL's ANY operator for list filtering
        # psycopg3 automatically adapts Python lists to PostgreSQL arrays
        clauses.append("org = ANY(%(orgs)s)")
        params["orgs"] = filters["orgs"]

    if filters.get("policy_type"):
        clauses.append("policy_type = %(policy_type)s")
        params["policy_type"] = filters["policy_type"]
    if filters.get("doc_name"):
        clauses.append("doc_name = %(doc_name)s")
        params["doc_name"] = filters["doc_name"]

    if not clauses:
        return "", params
    return " AND " + " AND ".join(clauses), params

def keyword_search(cur, q: str, top_k: int, filters: dict = None):
    """
    Performs full-text keyword search using PostgreSQL tsvector.
    
    Args:
        cur: Database cursor
        q: Query string
        top_k: Number of results to return
        filters: Optional dict with org, policy_type, doc_name filters
        
    Returns:
        List of results from the database
    """
    filters = filters or {}
    filter_sql, filter_params = build_filter_clauses(filters)
    
    sql = f"""
        SELECT doc_name, chunk_index, content, LEFT(content, 400) AS snippet, page, org,
               ts_rank(content_tsv, plainto_tsquery('english', %(q)s)) AS score
        FROM policy_chunks
        WHERE content_tsv @@ plainto_tsquery('english', %(q)s)
        {filter_sql}
        ORDER BY score DESC
        LIMIT %(top_k)s;
    """
    
    params = {"q": q, "top_k": top_k, **filter_params}
    cur.execute(sql, params)
    return cur.fetchall()

def vector_search(cur, q_vec: list[float], top_k: int, filters: dict = None):
    """
    Performs vector similarity search using pgvector.
    
    Args:
        cur: Database cursor
        q_vec: Query embedding vector
        top_k: Number of results to return
        filters: Optional dict with org, policy_type, doc_name filters
        
    Returns:
        List of results from the database
    """
    filters = filters or {}
    filter_sql, filter_params = build_filter_clauses(filters)
    
    sql = f"""
        SELECT doc_name, chunk_index, content, LEFT(content, 400) AS snippet, page, org,
               (embedding <=> %(q_vec)s::vector) AS distance
        FROM policy_chunks
        WHERE embedding IS NOT NULL
        {filter_sql}
        ORDER BY distance ASC
        LIMIT %(top_k)s;
    """
    
    params = {"q_vec": q_vec, "top_k": top_k, **filter_params}
    cur.execute(sql, params)
    return cur.fetchall()

def hybrid_search(q: str, top_k: int = 5, candidate_k: int = None, filters: dict = None, debug: bool = False):
    """
    Combines keyword, vector search, and reranking to return the best matches.
    
    Args:
        q: Query string
        top_k: Number of final results to return (FINAL_K)
        candidate_k: Number of candidates to retrieve before reranking
        filters: Optional dict with org, policy_type, doc_name filters
        debug: If True, return additional debug information
        
    Returns:
        Dictionary containing the query and ranked results
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set")

    # Use provided candidate_k or default
    retrieve_k = candidate_k or CANDIDATE_K
    filters = filters or {}

    # 1) Embed the query
    q_vec = get_embedding(q)

    keyword_rows = []
    vector_rows = []

    # 2) Retrieve Candidates (Retrieve Stage) with filters
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            keyword_rows = keyword_search(cur, q, retrieve_k, filters)
            vector_rows = vector_search(cur, q_vec, retrieve_k, filters)

    # 3) Merge + Dedupe
    merged = {}

    # Keyword results - now includes page and org
    for doc_name, chunk_index, content, snippet, page, org, score in keyword_rows:
        key = (doc_name, chunk_index)
        merged[key] = {
            "doc_name": doc_name,
            "chunk_index": chunk_index,
            "content": content,
            "snippet": snippet,
            "page": page,
            "org": org,
            "keyword_score": float(score),
            "vector_distance": None,
            "source": "keyword"
        }

    # Vector results - now includes page and org  
    for doc_name, chunk_index, content, snippet, page, org, dist in vector_rows:
        key = (doc_name, chunk_index)
        if key not in merged:
            merged[key] = {
                "doc_name": doc_name,
                "chunk_index": chunk_index,
                "content": content,
                "snippet": snippet,
                "page": page,
                "org": org,
                "keyword_score": None,
                "vector_distance": float(dist),
                "source": "vector"
            }
        else:
            merged[key]["vector_distance"] = float(dist)
            merged[key]["source"] = "both"

    candidates = list(merged.values())
    
    # If no candidates found, return early with warning
    if not candidates:
        return {
            "query": q,
            "filters": filters,
            "results": [],
            "warning": "No relevant policy content found for those filters. Try broader filters."
        }
    
    # 4) Rerank (Rerank Stage)
    try:
        ranked_results = rerank_documents(q, candidates, top_k=top_k)
    except Exception as e:
        # Fallback to vector ordering if reranking fails
        ranked_results = sorted(candidates, key=lambda x: x.get("vector_distance") or 999)[:top_k]
        for r in ranked_results:
            r["rerank_score"] = None
        warning = f"Reranker failed ({str(e)}), using vector fallback"
    else:
        warning = None

    response = {"query": q, "filters": filters, "results": ranked_results}
    
    if warning:
        response["warning"] = warning
    
    # Add debug information if requested
    if debug:
        response["debug"] = {
            "candidate_count": len(candidates),
            "keyword_count": len(keyword_rows),
            "vector_count": len(vector_rows),
            "retrieve_k": retrieve_k
        }

    return response