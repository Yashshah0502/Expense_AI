import os
from typing import Optional
import openai
from .policy_search import hybrid_search

# Initialize OpenAI client
openai.api_key = os.environ.get("OPENAI_API_KEY")

def generate_answer(
    query: str,
    filters: dict = None,
    candidate_k: int = 30,
    final_k: int = 5,
    group_by_org: bool = False,
):
    """
    Generate an answer to a policy question using retrieval + LLM.

    Args:
        query: User's question
        filters: Optional dict with org, policy_type, doc_name filters
        candidate_k: Number of candidates to retrieve
        final_k: Number of top results to use for generation
        group_by_org: If True, instruct the model to group answers by organization

    Returns:
        Dictionary with answer, sources, and metadata
    """
    filters = filters or {}
    
    # 1) Retrieve and rerank relevant chunks
    search_result = hybrid_search(
        q=query,
        top_k=final_k,
        candidate_k=candidate_k,
        filters=filters,
        debug=False
    )
    
    results = search_result.get("results", [])
    
    # Edge case: No results found
    if not results:
        return {
            "query": query,
            "filters": filters,
            "answer": "",
            "sources": [],
            "warning": search_result.get("warning", "No relevant policy content found for those filters. Try broader filters.")
        }
    
    # 2) Prepare citation blocks for LLM
    citation_blocks = []
    sources = []
    
    for i, chunk in enumerate(results, start=1):
        org = chunk.get("org", "UNKNOWN")
        doc_name = chunk.get("doc_name", "unknown.pdf")
        page = chunk.get("page", "?")
        content = chunk.get("content", "")
        score = chunk.get("rerank_score", 0)
        
        # Trim content to prevent token overflow
        content_trimmed = content.strip().replace("\n", " ")[:350]
        
        citation_blocks.append(
            f"[{org}] {doc_name} Pg {page}:\n{content_trimmed}"
        )
        
        sources.append({
            "doc_name": doc_name,
            "org": org,
            "page": page,
            "text_snippet": content_trimmed,
            "score": float(score) if score is not None else None
        })
    
    sources_text = "\n\n".join(citation_blocks)

    # 3) Build prompt with optional grouping instruction
    if group_by_org:
        system_instruction = """You are a policy assistant answering travel/procurement questions across multiple universities.

IMPORTANT: If policies differ by university, organize your answer by university (org). Show each organization separately with its specific policy and citations.

If all universities have the same policy, you can provide a single unified answer with citations from all sources.

Use only the following policy citations to answer. If unsure, say so."""
    else:
        system_instruction = """You are a policy assistant answering travel/procurement questions.

Use only the following policy citations to answer. If unsure, say so."""

    prompt = f"""{system_instruction}

Sources:
{sources_text}

Question:
{query}

Answer (with citations where relevant):"""
    
    # 4) Call LLM
    warning = None
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.3,
        )
        answer_text = response.choices[0].message.content.strip()
        
        # Check for empty/generic answer
        if not answer_text or len(answer_text) < 20:
            warning = "The model did not return a useful answer. Try adding broader filters or rephrasing."
            
    except Exception as e:
        answer_text = ""
        warning = f"LLM generation failed: {str(e)}"
    
    return {
        "query": query,
        "filters": filters,
        "answer": answer_text,
        "sources": sources,
        "warning": warning
    }
