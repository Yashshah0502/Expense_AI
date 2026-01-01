from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from dotenv import load_dotenv
import psycopg
import os

from rag.policy_search import hybrid_search
from rag.answer_gen import generate_answer
from app.policy.router_v1 import route_question
from app.schemas.router import AnswerResponse, Route

# Import new routers for Step 3.2 and Step 4
from app.routes import sql_debug, copilot

load_dotenv()
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Include new routers
app.include_router(sql_debug.router, tags=["debug"])
app.include_router(copilot.router, prefix="/copilot", tags=["copilot"])

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
    orgs: Optional[str] = Query(None, description="Filter by multiple orgs (comma-separated, e.g., 'ASU,Stanford')"),
    policy_type: Optional[str] = Query(None, description="Filter by type (travel/procurement/general)"),
    doc_name: Optional[str] = Query(None, description="Filter to specific PDF filename"),
    candidate_k: int = Query(30, description="Number of candidates to retrieve"),
    final_k: int = Query(5, alias="top_k", description="Number of final results"),
    debug: bool = Query(False, description="Include debug information"),
):
    """
    Search policy documents with optional filters.
    Returns ranked chunks with metadata.
    Supports multi-org filtering via 'orgs' parameter.
    """
    try:
        filters = {}
        if org:
            filters["org"] = org.upper()
        elif orgs:
            # Parse comma-separated orgs
            orgs_list = [o.strip().upper() for o in orgs.split(",") if o.strip()]
            filters["orgs"] = orgs_list
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

@app.post("/policy/answer", response_model=AnswerResponse)
def policy_answer(
    q: str = Query(..., min_length=2, description="Question to answer"),
    org: Optional[str] = Query(None, description="Filter by org/university"),
    policy_type: Optional[str] = Query(None, description="Filter by type"),
    doc_name: Optional[str] = Query(None, description="Filter to specific PDF"),
    candidate_k: int = Query(30, description="Number of candidates to retrieve"),
    final_k: int = Query(5, description="Number of sources to use for answer"),
):
    """
    Answer a policy question using retrieval + LLM generation with intelligent routing.
    Returns a structured answer with citations and routing information.
    """
    # Route the question to determine the appropriate handling
    decision = route_question(q, org=org, policy_type=policy_type, doc_name=doc_name)

    # Handle SQL intent (not yet implemented)
    if decision.route == Route.SQL_NOT_READY:
        return AnswerResponse(
            status="needs_sql",
            query=q,
            route=decision.route,
            filters=decision.filters,
            warning="This question needs expense/fact data (SQL). Policy docs alone may not answer it yet.",
        )

    # Handle clarification requests
    if decision.route == Route.CLARIFY:
        return AnswerResponse(
            status="needs_clarification",
            query=q,
            route=decision.route,
            filters=decision.filters,
            clarify_question=decision.clarify_question,
        )

    # RAG routes (RAG_FILTERED, RAG_ALL, or MULTI_ORG_POLICY) -> call existing answer pipeline
    # Convert PolicyFilters to dict for generate_answer
    filters_dict = {}
    if decision.filters.org:
        filters_dict["org"] = decision.filters.org.upper()
    elif decision.filters.orgs:
        filters_dict["orgs"] = [o.upper() for o in decision.filters.orgs]
    if decision.filters.policy_type:
        filters_dict["policy_type"] = decision.filters.policy_type.lower()
    if decision.filters.doc_name:
        filters_dict["doc_name"] = decision.filters.doc_name

    result = generate_answer(
        query=q,
        filters=filters_dict,
        candidate_k=candidate_k,
        final_k=final_k,
        group_by_org=(decision.route in [Route.RAG_ALL, Route.MULTI_ORG_POLICY]),
        per_org_retrieval=(decision.route == Route.MULTI_ORG_POLICY),
    )

    # Handle no results case
    if not result.get("sources"):
        return AnswerResponse(
            status="no_results",
            query=q,
            route=decision.route,
            filters=decision.filters,
            warning="No relevant policy chunks found. Try specifying a university or different keywords.",
        )

    # Return successful result
    return AnswerResponse(
        status="ok",
        query=q,
        route=decision.route,
        filters=decision.filters,
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        warning=result.get("warning"),
    )
