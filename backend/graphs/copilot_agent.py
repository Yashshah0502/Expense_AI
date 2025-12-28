"""
LangGraph ReAct agent for intelligent question answering.
Combines policy search and SQL tools to answer user questions.
"""

import os
from typing import TypedDict, Annotated, Sequence, Literal, Dict, Any, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
import psycopg

from rag.policy_search import hybrid_search
from rag.rerank import rerank_documents
from tools.sql_tools import (
    get_expense_totals,
    get_expense_samples,
    get_case_timeline,
    find_possible_duplicates,
)


# Configuration
MAX_TOOL_CALLS = 6  # Prevent infinite loops
DB_URL = os.getenv("DATABASE_URL")


class AgentState(TypedDict):
    """State for the agent graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    tool_call_count: int


# Define tools


@tool
def policy_tool(
    question: str,
    org: str | None = None,
    policy_type: str | None = None
) -> Dict[str, Any]:
    """
    Search policy documents for rules and guidelines.
    Returns relevant policy excerpts with citations.
    Use this when the question is about policy rules, guidelines, or requirements.

    Args:
        question: The question about policy
        org: Organization/university name to filter by
        policy_type: Type of policy (travel/procurement/general)

    Returns:
        Dict with answer_hint and sources
    """
    filters = {}
    if org:
        filters["org"] = org.upper()
    if policy_type:
        filters["policy_type"] = policy_type.lower()

    # Search for relevant chunks
    search_results = hybrid_search(
        q=question,
        top_k=20,
        candidate_k=30,
        filters=filters,
        debug=False,
    )

    if not search_results.get("chunks"):
        return {
            "answer_hint": f"No policy documents found for {org or 'any organization'}.",
            "sources": []
        }

    # Rerank results
    reranked = rerank_documents(
        query=question,
        documents=search_results["chunks"],
        top_k=5
    )

    # Format sources
    sources = []
    for chunk in reranked:
        sources.append({
            "doc_name": chunk.get("doc_name", ""),
            "org": chunk.get("org", ""),
            "policy_type": chunk.get("policy_type"),
            "page": chunk.get("page", 0),
            "chunk_index": chunk.get("chunk_index"),
            "score": chunk.get("rerank_score", chunk.get("score")),
            "snippet": chunk.get("text", chunk.get("snippet", ""))[:300],  # Limit snippet length
        })

    # Create hint from top chunks
    evidence = "\n\n".join([
        f"[{s['org']}] {s['doc_name']} (page {s['page']}): {s['snippet']}"
        for s in sources[:3]
    ])

    return {
        "answer_hint": f"Found {len(sources)} relevant policy excerpts:\n{evidence}",
        "sources": sources
    }


@tool
def sql_totals_tool(
    org: str,
    employee_id: str | None = None,
    group_by: str = "category"
) -> Dict[str, Any]:
    """
    Get expense totals grouped by a dimension (category, merchant, employee, etc.).
    Use this when the question asks about spending totals, aggregates, or breakdowns.

    Args:
        org: Organization name (required)
        employee_id: Employee ID to filter by (optional)
        group_by: Dimension to group by (category, merchant, currency, employee_id, report_id)

    Returns:
        Dict with ok, data (list of groups with totals), and warning
    """
    if not DB_URL:
        return {"ok": False, "data": [], "warning": "Database not configured"}

    with psycopg.connect(DB_URL) as conn:
        return get_expense_totals(
            conn=conn,
            org=org,
            employee_id=employee_id,
            group_by=group_by
        )


@tool
def sql_samples_tool(
    org: str,
    employee_id: str | None = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get sample expense rows to see detailed expense data.
    Use this when the question asks about specific expenses or needs examples.

    Args:
        org: Organization name (required)
        employee_id: Employee ID to filter by (optional)
        limit: Number of samples to return (default 10, max 50)

    Returns:
        Dict with ok, data (list of expense rows), and warning
    """
    if not DB_URL:
        return {"ok": False, "data": [], "warning": "Database not configured"}

    with psycopg.connect(DB_URL) as conn:
        return get_expense_samples(
            conn=conn,
            org=org,
            employee_id=employee_id,
            limit=limit
        )


@tool
def sql_timeline_tool(
    org: str,
    case_id: str
) -> Dict[str, Any]:
    """
    Get event timeline for an expense case.
    Use this when the question asks about the approval process, workflow, or timeline.

    Args:
        org: Organization name (required)
        case_id: Case ID to get timeline for (required)

    Returns:
        Dict with ok, data (list of events), and warning
    """
    if not DB_URL:
        return {"ok": False, "data": [], "warning": "Database not configured"}

    with psycopg.connect(DB_URL) as conn:
        return get_case_timeline(
            conn=conn,
            org=org,
            case_id=case_id
        )


@tool
def sql_duplicates_tool(
    org: str,
    window_days: int = 7
) -> Dict[str, Any]:
    """
    Find possible duplicate expenses.
    Use this when the question asks about duplicate expenses or potential fraud.

    Args:
        org: Organization name (required)
        window_days: Window in days for detecting duplicates (default 7)

    Returns:
        Dict with ok, data (list of duplicate groups), and warning
    """
    if not DB_URL:
        return {"ok": False, "data": [], "warning": "Database not configured"}

    with psycopg.connect(DB_URL) as conn:
        return find_possible_duplicates(
            conn=conn,
            org=org,
            window_days=window_days
        )


# All tools
tools = [
    policy_tool,
    sql_totals_tool,
    sql_samples_tool,
    sql_timeline_tool,
    sql_duplicates_tool,
]


# Agent graph


def create_agent_graph():
    """Create the LangGraph agent graph."""

    # System prompt for intelligent routing
    system_message = """You are an expense policy and data assistant. You help users understand policy rules and analyze expense data.

You have access to these tools:
- policy_tool: Search policy documents for rules and guidelines
- sql_totals_tool: Get expense totals grouped by category, merchant, etc.
- sql_samples_tool: Get sample expense rows for detailed analysis
- sql_timeline_tool: Get event timeline for an expense case
- sql_duplicates_tool: Find possible duplicate expenses

Guidelines:
1. For policy questions (rules, guidelines, limits) → use policy_tool
2. For expense totals/aggregates → use sql_totals_tool
3. For specific expense examples → use sql_samples_tool
4. For approval workflows/timelines → use sql_timeline_tool (requires case_id)
5. For duplicate detection → use sql_duplicates_tool

Important:
- If a SQL tool requires org or employee_id but you don't have it, ask the user ONE clarifying question
- NEVER fabricate numbers, amounts, or policy rules without sources
- Cite sources using format: [Org] doc_name (page X)
- If you can't answer confidently, say so and explain what information you need
- Combine tools when needed (e.g., policy + SQL for compliance checks)

Be concise and helpful. Provide direct answers with proper citations.
"""

    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: AgentState) -> AgentState:
        """Call the LLM with tools."""
        # Check tool call limit
        if state.get("tool_call_count", 0) >= MAX_TOOL_CALLS:
            return {
                "messages": [
                    AIMessage(content="I've reached my tool call limit. Please rephrase your question or provide more specific filters.")
                ],
                "tool_call_count": state.get("tool_call_count", 0)
            }

        messages = [{"role": "system", "content": system_message}] + list(state["messages"])
        response = llm_with_tools.invoke(messages)

        # Increment tool call count if tools were called
        new_count = state.get("tool_call_count", 0)
        if hasattr(response, "tool_calls") and response.tool_calls:
            new_count += len(response.tool_calls)

        return {
            "messages": [response],
            "tool_call_count": new_count
        }

    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        """Decide whether to continue or end."""
        last_message = state["messages"][-1]

        # If the LLM makes tool calls, continue to tools node
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # Otherwise, end
        return "end"

    # Build graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()


# Initialize graph (singleton)
_agent_graph = None


def get_agent_graph():
    """Get or create the agent graph."""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph


def run_agent(question: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the agent to answer a question.

    Args:
        question: The user's question
        context: Context dict with org, employee_id, case_id, policy_type, etc.

    Returns:
        Dict with:
        - answer: str (the final answer)
        - tools_called: List[str] (names of tools called)
        - policy_sources: List[Dict] (policy sources used)
        - sql_results: Dict (raw SQL results)
        - warnings: List[str] (any warnings)
    """
    # Prepend context to question if available
    context_str = ""
    if context.get("org"):
        context_str += f"Organization: {context['org']}\n"
    if context.get("employee_id"):
        context_str += f"Employee ID: {context['employee_id']}\n"
    if context.get("case_id"):
        context_str += f"Case ID: {context['case_id']}\n"
    if context.get("policy_type"):
        context_str += f"Policy Type: {context['policy_type']}\n"

    if context_str:
        full_question = f"{context_str}\nQuestion: {question}"
    else:
        full_question = question

    # Run the agent
    graph = get_agent_graph()
    initial_state: AgentState = {
        "messages": [HumanMessage(content=full_question)],
        "tool_call_count": 0
    }

    final_state = graph.invoke(initial_state)

    # Extract results from final state
    messages = final_state["messages"]

    # Get final answer (last AI message)
    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            answer = msg.content
            break

    # Extract tools called
    tools_called = []
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            for tc in msg.tool_calls:
                tools_called.append(tc["name"])

    # Extract policy sources and SQL results from tool messages
    policy_sources = []
    sql_results = {
        "totals": None,
        "samples": None,
        "timeline": None,
        "duplicates": None
    }

    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                content = eval(msg.content) if isinstance(msg.content, str) else msg.content

                # Check if this is a policy tool result
                if isinstance(content, dict) and "sources" in content:
                    policy_sources.extend(content["sources"])

                # Check if this is a SQL tool result
                if isinstance(content, dict) and "data" in content:
                    # Determine which SQL tool this is from
                    if msg.name == "sql_totals_tool":
                        sql_results["totals"] = content["data"]
                    elif msg.name == "sql_samples_tool":
                        sql_results["samples"] = content["data"]
                    elif msg.name == "sql_timeline_tool":
                        sql_results["timeline"] = content["data"]
                    elif msg.name == "sql_duplicates_tool":
                        sql_results["duplicates"] = content["data"]
            except:
                pass

    # Extract warnings
    warnings = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                content = eval(msg.content) if isinstance(msg.content, str) else msg.content
                if isinstance(content, dict) and content.get("warning"):
                    warnings.append(content["warning"])
            except:
                pass

    return {
        "answer": answer or "I couldn't generate an answer. Please try rephrasing your question.",
        "tools_called": tools_called,
        "policy_sources": policy_sources,
        "sql_results": sql_results,
        "warnings": warnings
    }
