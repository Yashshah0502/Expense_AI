import re
from typing import Optional, Dict, List, Tuple

from app.schemas.router import RouterDecision, PolicyFilters, Route

# Canonical org names you store in DB (must match your org column values)
ORG_ALIASES: Dict[str, List[str]] = {
    "ASU": ["asu", "arizona state", "arizona state university"],
    "Columbia": ["columbia", "columbia university"],
    "Michigan": ["michigan", "university of michigan", "umich"],
    "Yale": ["yale", "yale university"],
    "Princeton": ["princeton", "princeton university"],
    "NYU": ["nyu", "new york university"],
    "Stanford": ["stanford", "stanford university"],
    "Rutgers": ["rutgers", "rutgers university"],
}

SQL_INTENT_KEYWORDS = [
    "my expense", "my expenses", "expense status", "status of", "report id", "expense report",
    "submitted", "approved", "rejected", "reimbursement status", "timeline", "how much did i spend",
    "total spend", "show my", "list my",
]

# Optional: infer policy_type (keep conservative; don't over-filter)
POLICY_TYPE_KEYWORDS = {
    "travel": ["travel", "lodging", "hotel", "flight", "airfare", "rental car", "mileage", "per diem"],
    "procurement": ["procurement", "p-card", "p card", "purchase", "vendor", "invoice"],
}

# If question sounds like it expects ONE definitive policy answer, ask org (instead of RAG_ALL).
SINGLE_POLICY_EXPECTATION_TRIGGERS = [
    "is it allowed", "is it reimbursable", "can i", "can we", "allowed", "reimbursable", "proof of payment",
]

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def extract_orgs(question: str) -> List[str]:
    q = _norm(question)
    found: List[str] = []
    for canonical, aliases in ORG_ALIASES.items():
        for a in aliases:
            # word boundary-ish match
            if re.search(rf"(^|[^a-z0-9]){re.escape(a)}([^a-z0-9]|$)", q):
                found.append(canonical)
                break
    # unique preserve order
    seen = set()
    out = []
    for x in found:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def infer_policy_type(question: str) -> Optional[str]:
    q = _norm(question)
    hits: List[Tuple[str, int]] = []
    for ptype, kws in POLICY_TYPE_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in q)
        if score:
            hits.append((ptype, score))
    if not hits:
        return None
    hits.sort(key=lambda x: x[1], reverse=True)
    # Only set if it's clearly leaning one way
    return hits[0][0] if hits[0][1] >= 2 else hits[0][0]

def has_sql_intent(question: str) -> bool:
    q = _norm(question)
    return any(k in q for k in SQL_INTENT_KEYWORDS)

def expects_single_policy_answer(question: str) -> bool:
    q = _norm(question)
    # if user asks to compare, don't clarify—return RAG_ALL grouped
    if " vs " in q or "compare" in q or "difference" in q:
        return False
    return any(t in q for t in SINGLE_POLICY_EXPECTATION_TRIGGERS)

def route_question(
    question: str,
    org: Optional[str] = None,
    policy_type: Optional[str] = None,
    doc_name: Optional[str] = None,
) -> RouterDecision:
    q = question.strip()

    # Explicit query params always win
    explicit_filters = PolicyFilters(org=org, policy_type=policy_type, doc_name=doc_name)

    if has_sql_intent(q):
        return RouterDecision(
            route=Route.SQL_NOT_READY,
            filters=explicit_filters,
            reason="Detected SQL/user-specific expense intent; SQL not integrated yet.",
        )

    # Infer filters only if not explicitly provided
    inferred_orgs = extract_orgs(q) if not org else []
    inferred_policy_type = infer_policy_type(q) if not policy_type else None

    filters = PolicyFilters(
        org=org or (inferred_orgs[0] if len(inferred_orgs) == 1 else None),
        policy_type=policy_type or inferred_policy_type,
        doc_name=doc_name,
    )

    # Multiple orgs mentioned => RAG_ALL (answer grouped by org)
    if len(inferred_orgs) >= 2 and not org:
        return RouterDecision(
            route=Route.RAG_ALL,
            filters=PolicyFilters(org=None, policy_type=filters.policy_type, doc_name=doc_name),
            reason=f"Multiple orgs detected {inferred_orgs}; return cross-org answer.",
        )

    # If we have org => filtered
    if filters.org:
        return RouterDecision(
            route=Route.RAG_FILTERED,
            filters=filters,
            reason="Org available; use filtered RAG.",
        )

    # No org: either clarify or answer across all orgs
    if expects_single_policy_answer(q):
        orgs_list = ", ".join(ORG_ALIASES.keys())
        return RouterDecision(
            route=Route.CLARIFY,
            filters=filters,
            clarify_question=f"Which university policy should I use? ({orgs_list})",
            reason="No org provided but question expects one definitive policy.",
        )

    return RouterDecision(
        route=Route.RAG_ALL,
        filters=filters,
        reason="No org provided; answer across all universities (group by org in response).",
    )
