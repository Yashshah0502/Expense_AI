"""
Pydantic schemas for /copilot/answer endpoint.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class CopilotRequest(BaseModel):
    """Request schema for copilot answer endpoint."""
    question: str = Field(..., min_length=1, description="Question to answer")
    org: Optional[str] = Field(None, description="Organization/university filter")
    employee_id: Optional[str] = Field(None, description="Employee ID for expense queries")
    case_id: Optional[str] = Field(None, description="Case ID for event timeline queries")
    policy_type: Optional[str] = Field(None, description="Policy type filter (travel/procurement/general)")
    debug: bool = Field(False, description="Include debug information")


class PolicySource(BaseModel):
    """Schema for a policy document source/citation."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doc_name": "stanford_travel_policy.pdf",
                "org": "Stanford",
                "policy_type": "travel",
                "page": 5,
                "chunk_index": 12,
                "score": 0.95,
                "snippet": "Business class is allowed for international flights exceeding 8 hours..."
            }
        }
    )

    doc_name: str = Field(..., description="PDF filename")
    org: str = Field(..., description="University/organization name")
    policy_type: Optional[str] = Field(None, description="Type of policy document")
    page: int | str = Field(..., description="Page number in the document")
    chunk_index: Optional[int] = Field(None, description="Chunk index within the document")
    score: Optional[float] = Field(None, description="Relevance/rerank score (0-1)")
    snippet: str = Field(..., description="Relevant text excerpt from the document")


class Routing(BaseModel):
    """Information about which tools were used to answer the question."""
    used_policy: bool = Field(..., description="Whether policy search was used")
    used_sql: bool = Field(..., description="Whether SQL queries were executed")
    tools_called: List[str] = Field(..., description="List of tool names called by the agent")


class SQLResults(BaseModel):
    """Raw SQL query results returned by the agent."""
    totals: Optional[List[Dict[str, Any]]] = Field(None, description="Results from expense totals query")
    samples: Optional[List[Dict[str, Any]]] = Field(None, description="Results from expense samples query")
    timeline: Optional[List[Dict[str, Any]]] = Field(None, description="Results from event timeline query")
    duplicates: Optional[List[Dict[str, Any]]] = Field(None, description="Results from duplicates query")


class CopilotResponse(BaseModel):
    """Response schema for copilot answer endpoint."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "Based on Stanford's travel policy, business class is allowed for international flights exceeding 8 hours. Your expense of $1,200 for a flight to London complies with this policy.",
                "routing": {
                    "used_policy": True,
                    "used_sql": True,
                    "tools_called": ["policy_tool", "sql_samples_tool"]
                },
                "policy_sources": [
                    {
                        "doc_name": "stanford_travel_policy.pdf",
                        "org": "Stanford",
                        "policy_type": "travel",
                        "page": 5,
                        "chunk_index": 12,
                        "score": 0.95,
                        "snippet": "Business class is allowed for international flights exceeding 8 hours..."
                    }
                ],
                "sql_results": {
                    "totals": None,
                    "samples": [
                        {
                            "expense_id": 123,
                            "employee_id": "EMP001",
                            "amount": "1200.00",
                            "category": "Travel"
                        }
                    ],
                    "timeline": None,
                    "duplicates": None
                },
                "follow_up": None,
                "warnings": []
            }
        }
    )

    answer: str = Field(..., description="Natural language answer to the question")
    routing: Routing = Field(..., description="Information about tools used")
    policy_sources: List[PolicySource] = Field(default_factory=list, description="Policy document sources cited")
    sql_results: SQLResults = Field(..., description="Raw SQL query results")
    follow_up: Optional[str] = Field(None, description="Follow-up question if clarification needed")
    warnings: List[str] = Field(default_factory=list, description="Warnings or caveats about the answer")
