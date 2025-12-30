from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class Route(str, Enum):
    RAG_FILTERED = "RAG_FILTERED"      # use filters (org/policy_type/doc_name)
    RAG_ALL = "RAG_ALL"                # no org filter; answer across orgs
    MULTI_ORG_POLICY = "MULTI_ORG_POLICY"  # multi-org comparison; run per-org retrieval
    CLARIFY = "CLARIFY"                # ask one question (usually missing org)
    SQL_NOT_READY = "SQL_NOT_READY"    # user asked for factual expense data


class PolicyFilters(BaseModel):
    org: Optional[str] = None
    orgs: Optional[List[str]] = None  # For multi-org queries
    policy_type: Optional[str] = None
    doc_name: Optional[str] = None


class RouterDecision(BaseModel):
    route: Route
    filters: PolicyFilters = Field(default_factory=PolicyFilters)
    clarify_question: Optional[str] = None
    reason: str = ""


class Source(BaseModel):
    """Schema for a policy document source/citation"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doc_name": "stanford_travel_policy.pdf",
                "org": "Stanford",
                "page": 5,
                "text_snippet": "Business class is allowed for international flights exceeding 8 hours...",
                "score": 0.95
            }
        }
    )

    doc_name: str = Field(..., description="PDF filename")
    org: str = Field(..., description="University/organization name")
    page: int | str = Field(..., description="Page number in the document")
    text_snippet: str = Field(..., description="Relevant text excerpt from the document")
    score: Optional[float] = Field(None, description="Relevance/rerank score (0-1)")


class AnswerResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "query": "For Stanford, is business class allowed?",
                "route": "RAG_FILTERED",
                "filters": {
                    "org": "Stanford",
                    "policy_type": None,
                    "doc_name": None
                },
                "answer": "Yes, Stanford allows business class for international flights exceeding 8 hours. [Stanford] stanford_travel_policy.pdf Pg 5",
                "sources": [
                    {
                        "doc_name": "stanford_travel_policy.pdf",
                        "org": "Stanford",
                        "page": 5,
                        "text_snippet": "Business class is allowed for international flights exceeding 8 hours...",
                        "score": 0.95
                    }
                ],
                "clarify_question": None,
                "warning": None
            }
        }
    )

    status: str = Field(..., description="Response status: ok | needs_clarification | needs_sql | no_results")
    query: str = Field(..., description="The original user question")
    route: Route = Field(..., description="The routing decision made by the router")
    filters: PolicyFilters = Field(..., description="Filters applied for this query")

    answer: Optional[str] = Field(None, description="LLM-generated answer with citations")
    sources: List[Source] = Field(default_factory=list, description="Source documents used to generate the answer")

    clarify_question: Optional[str] = Field(None, description="Follow-up question if clarification is needed")
    warning: Optional[str] = Field(None, description="Warning or error message if applicable")
