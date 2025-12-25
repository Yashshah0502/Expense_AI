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
    # We prefer 'content' (full text) if available, capped at 2000 chars for performance.
    # Fallback to 'snippet' if 'content' is missing.
    pairs = []
    for doc in documents:
        text_source = doc.get("content") or doc.get("snippet") or ""
        # Cap at 1024 chars as recommended for BAAI/bge-reranker-v2-m3
        text = text_source[:1024]
        pairs.append([query, text])
    
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
