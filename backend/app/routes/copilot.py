"""
User-facing copilot endpoint using LangGraph agent.
Provides intelligent question answering across policy documents and expense data.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.copilot import CopilotRequest, CopilotResponse, PolicySource, Routing, SQLResults
from graphs.copilot_agent import run_agent


router = APIRouter()


@router.post("/answer", response_model=CopilotResponse)
def copilot_answer(
    q: str = Query(..., min_length=1, description="Question to answer"),
    org: Optional[str] = Query(None, description="Organization/university filter"),
    employee_id: Optional[str] = Query(None, description="Employee ID for expense queries"),
    case_id: Optional[str] = Query(None, description="Case ID for event timeline queries"),
    policy_type: Optional[str] = Query(None, description="Policy type filter (travel/procurement/general)"),
    debug: bool = Query(False, description="Include debug information"),
):
    """
    Answer a question using intelligent routing via LangGraph agent.

    The agent can:
    - Search policy documents for rules and guidelines
    - Query expense data (totals, samples, duplicates)
    - Query event timelines for expense cases
    - Combine multiple data sources for comprehensive answers

    The agent will ask for clarification if required information is missing.
    """
    # Build context from request parameters
    context = {}
    if org:
        context["org"] = org
    if employee_id:
        context["employee_id"] = employee_id
    if case_id:
        context["case_id"] = case_id
    if policy_type:
        context["policy_type"] = policy_type
    if debug:
        context["debug"] = debug

    # Run the agent
    result = run_agent(question=q, context=context)

    # Extract routing information
    routing = Routing(
        used_policy="policy_tool" in result["tools_called"],
        used_sql=any(
            tool in result["tools_called"]
            for tool in ["sql_totals_tool", "sql_samples_tool", "sql_timeline_tool", "sql_duplicates_tool"]
        ),
        tools_called=result["tools_called"],
    )

    # Convert policy sources
    policy_sources = [
        PolicySource(
            doc_name=src.get("doc_name", ""),
            org=src.get("org", ""),
            policy_type=src.get("policy_type"),
            page=src.get("page", 0),
            chunk_index=src.get("chunk_index"),
            score=src.get("score"),
            snippet=src.get("snippet", src.get("text_snippet", "")),
        )
        for src in result.get("policy_sources", [])
    ]

    # Extract SQL results
    sql_results = SQLResults(
        totals=result.get("sql_results", {}).get("totals"),
        samples=result.get("sql_results", {}).get("samples"),
        timeline=result.get("sql_results", {}).get("timeline"),
        duplicates=result.get("sql_results", {}).get("duplicates"),
    )

    # Detect if agent is asking for clarification
    follow_up = None
    answer_lower = result["answer"].lower()
    if any(phrase in answer_lower for phrase in [
        "which employee", "what employee", "who are you asking about",
        "which case", "what case", "case id", "employee id",
        "need to know", "can you specify", "can you provide"
    ]):
        follow_up = result["answer"]

    return CopilotResponse(
        answer=result["answer"],
        routing=routing,
        policy_sources=policy_sources,
        sql_results=sql_results,
        follow_up=follow_up,
        warnings=result.get("warnings", []),
    )
