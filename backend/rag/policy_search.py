import os
import psycopg
from .embeddings import get_embedding

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
    Combines keyword search and vector search to return the best matches.
    
    Args:
        q: Query string
        top_k: Number of results to return
        
    Returns:
        Dictionary containing the query and ranked results
    """
    # Use environment variable for DB connection, assuming it's loaded in main or here
    # It's better to load it here in case this is called independently, 
    # but usually load_dotenv() is called at app startup. 
    # For safety, we can get it from os.environ
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set")

    # 1) Embed the query
    q_vec = get_embedding(q)

    keyword_rows = []
    vector_rows = []

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 2) Keyword search
            keyword_rows = keyword_search(cur, q, top_k)
            
            # 3) Vector search
            vector_rows = vector_search(cur, q_vec, top_k)

    # 4) Merge + dedupe
    merged = {}

    # Keyword scores: higher is better
    for doc_name, chunk_index, snippet, score in keyword_rows:
        key = (doc_name, chunk_index)
        merged[key] = {
            "doc_name": doc_name,
            "chunk_index": chunk_index,
            "snippet": snippet,
            "keyword_score": float(score),
            "vector_distance": None,
        }

    # Vector distances: lower is better
    for doc_name, chunk_index, snippet, dist in vector_rows:
        key = (doc_name, chunk_index)
        if key not in merged:
            merged[key] = {
                "doc_name": doc_name,
                "chunk_index": chunk_index,
                "snippet": snippet,
                "keyword_score": None,
                "vector_distance": float(dist),
            }
        else:
            merged[key]["vector_distance"] = float(dist)

    # 5) Rank: prefer items in both, then use a combined score or heuristic
    # This ranking logic perfectly matches the original request
    def rank(item):
        both = (item["keyword_score"] is not None) and (item["vector_distance"] is not None)
        # Lower distance is better; use big default if missing
        dist = item["vector_distance"] if item["vector_distance"] is not None else 999.0
        # Higher keyword score is better; use 0 default if missing
        kw = item["keyword_score"] if item["keyword_score"] is not None else 0.0
        # Tuple sort: (is_in_both desc, distance asc, kw_score desc)
        # Python sorts tuples element-by-element.
        # We want `both`=True first (1 vs 0).
        # We want lower distance first. To sort desc, we negate dist?
        # Wait, the original code used `key=rank, reverse=True`.
        # So we want HIGHER values to be better.
        # Both=True (1) > Both=False (0). Correct.
        # Distance: We want LOWER distance. So -dist is HIGHER (better). Correct.
        # Keyword: We want HIGHER keyword score. Correct.
        return (1 if both else 0, -dist, kw)

    results = list(merged.values())
    results.sort(key=rank, reverse=True)

    # Add source label
    for r in results:
        if r["keyword_score"] is not None and r["vector_distance"] is not None:
            r["source"] = "both"
        elif r["keyword_score"] is not None:
            r["source"] = "keyword"
        else:
            r["source"] = "vector"

    return {"query": q, "results": results[:top_k]}
