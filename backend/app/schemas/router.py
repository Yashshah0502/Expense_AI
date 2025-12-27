from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class Route(str, Enum):
    RAG_FILTERED = "RAG_FILTERED"      # use filters (org/policy_type/doc_name)
    RAG_ALL = "RAG_ALL"                # no org filter; answer across orgs
    CLARIFY = "CLARIFY"                # ask one question (usually missing org)
    SQL_NOT_READY = "SQL_NOT_READY"    # user asked for factual expense data


class PolicyFilters(BaseModel):
    org: Optional[str] = None
    policy_type: Optional[str] = None
    doc_name: Optional[str] = None


class RouterDecision(BaseModel):
    route: Route
    filters: PolicyFilters = Field(default_factory=PolicyFilters)
    clarify_question: Optional[str] = None
    reason: str = ""


class AnswerResponse(BaseModel):
    status: str  # "ok" | "needs_clarification" | "needs_sql" | "no_results"
    query: str
    route: Route
    filters: PolicyFilters

    answer: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)  # keep flexible for your existing shape

    clarify_question: Optional[str] = None
    warning: Optional[str] = None
