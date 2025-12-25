from FlagEmbedding import FlagReranker

# Global singleton for the reranker model
_reranker_model = None

def get_reranker_model():
    """Returns the lazy-loaded global reranker model."""
    global _reranker_model
    if _reranker_model is None:
        # Load the cross-encoder model
        # use_fp16=True helps with performance if GPU is available, 
        # but on CPU it mostly ignores it or falls back. 
        # We'll stick to defaults to be safe on Mac (MPS or CPU).
        _reranker_model = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=False)
    return _reranker_model

def rerank_documents(query: str, documents: list[dict], top_k: int) -> list[dict]:
    """
    Reranks a list of candidate documents based on the query.
    
    Args:
        query: The search query.
        documents: List of document dicts. Each dict must have 'doc_name' and 'snippet' (or 'content').
                   We will use 'snippet' for reranking as it's the text content.
        top_k: Number of results to return after reranking.
        
    Returns:
        Top K documents sorted by rerank score.
    """
    if not documents:
        return []

    reranker = get_reranker_model()
    
    # Prepare pairs for the cross-encoder: [[query, text], [query, text], ...]
    # We use 'snippet' which comes from the SQL query (LEFT(content, 400)). 
    # Ideally for reranking we might want more context, but let's stick to what we retrieved.
    # If possible, we should maybe retrieve full content for candidates if snippet is too short,
    # but snippet=400 chars might be enough for a strong signal. 
    # Actually, the user's SEARCH query returns `snippet`. 
    # Let's check `policy_search.py`: "LEFT(content, 400) AS snippet".
    # Cross-encoder works best with more context, but 400 chars is okay.
    
    pairs = [[query, doc["snippet"]] for doc in documents]
    
    # Compute scores
    scores = reranker.compute_score(pairs)
    
    # If only one document, scores might be a float? No, usually list.
    if isinstance(scores, float):
        scores = [scores]
        
    # Attach scores to documents
    for doc, score in zip(documents, scores):
        doc["rerank_score"] = score
        
    # Sort by score descending
    documents.sort(key=lambda x: x["rerank_score"], reverse=True)
    
    return documents[:top_k]
