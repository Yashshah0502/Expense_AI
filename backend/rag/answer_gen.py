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
    per_org_retrieval: bool = False,
):
    """
    Generate an answer to a policy question using retrieval + LLM.

    Args:
        query: User's question
        filters: Optional dict with org, orgs, policy_type, doc_name filters
        candidate_k: Number of candidates to retrieve per org
        final_k: Number of top results to use for generation (total or per org)
        group_by_org: If True, instruct the model to group answers by organization
        per_org_retrieval: If True, run separate retrieval for each org (for MULTI_ORG_POLICY)

    Returns:
        Dictionary with answer, sources, and metadata
    """
    filters = filters or {}

    # If per_org_retrieval is enabled, run retrieval for each org separately
    if per_org_retrieval and filters.get("orgs"):
        orgs = filters["orgs"]
        all_results = []

        # Run retrieval for each org with higher candidate_k to avoid missing any university
        per_org_candidate_k = candidate_k if candidate_k > 20 else 25  # Use at least 20-30 per org
        per_org_final_k = max(3, final_k // len(orgs))  # Get proportional results per org

        for org in orgs:
            org_filters = {**filters, "org": org}
            # Remove 'orgs' key to avoid conflict
            org_filters.pop("orgs", None)

            org_search = hybrid_search(
                q=query,
                top_k=per_org_final_k,
                candidate_k=per_org_candidate_k,
                filters=org_filters,
                debug=False
            )

            org_results = org_search.get("results", [])
            all_results.extend(org_results)

        results = all_results
    else:
        # Standard retrieval (single org or all orgs at once)
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
        if per_org_retrieval:
            # Enhanced prompt for per-org retrieval with structured summary format
            system_instruction = """You are a policy assistant answering travel/procurement questions across multiple universities.

CRITICAL INSTRUCTIONS FOR MULTI-ORG COMPARISON:
1. Organize your answer BY UNIVERSITY (one section per org)
2. For EACH university, provide a clear summary:
   - **Allowed**: If the policy explicitly allows it
   - **Not Allowed**: If the policy explicitly prohibits it
   - **Conditional**: If it's allowed under certain conditions (state the conditions)
   - **Not Found**: If no relevant policy information was found for this university

3. Format like this:
   **[University Name]**: Status (citation)
   - Brief explanation with specific details

4. ALWAYS include ALL universities from the sources, even if policy wasn't found.
5. Cite sources using format: [Org] doc_name (page X)

Use only the following policy citations to answer."""
        else:
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
            max_tokens=300,
            temperature=0.2,
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
