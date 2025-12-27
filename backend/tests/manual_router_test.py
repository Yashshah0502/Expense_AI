"""
Manual test script to demonstrate router integration
Run this to verify the /policy/answer endpoint logic works correctly
No external dependencies required beyond what's already in requirements.txt
"""
import sys
sys.path.insert(0, '..')

from app.policy.router_v1 import route_question
from app.schemas.router import Route, PolicyFilters, AnswerResponse


def test_router_to_response_flow():
    """
    Simulate the /policy/answer endpoint flow without FastAPI
    This demonstrates how the router integrates with the response model
    """
    print("=" * 60)
    print("TESTING ROUTER -> RESPONSE INTEGRATION")
    print("=" * 60)

    test_cases = [
        {
            "query": "What is my expense status for report 123?",
            "expected_route": Route.SQL_NOT_READY,
            "expected_status": "needs_sql"
        },
        {
            "query": "Is business class allowed?",
            "expected_route": Route.CLARIFY,
            "expected_status": "needs_clarification"
        },
        {
            "query": "For Stanford, is business class allowed?",
            "expected_route": Route.RAG_FILTERED,
            "expected_status": "ok"
        },
        {
            "query": "Compare ASU vs Yale meal per diem",
            "expected_route": Route.RAG_ALL,
            "expected_status": "ok"
        },
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['query']}")
        print("-" * 60)

        # Step 1: Route the question
        decision = route_question(test["query"])
        print(f"  Route: {decision.route}")
        print(f"  Filters: {decision.filters}")
        print(f"  Reason: {decision.reason}")

        # Step 2: Create appropriate response based on route
        if decision.route == Route.SQL_NOT_READY:
            response = AnswerResponse(
                status="needs_sql",
                query=test["query"],
                route=decision.route,
                filters=decision.filters,
                warning="This question needs expense/fact data (SQL).",
            )
        elif decision.route == Route.CLARIFY:
            response = AnswerResponse(
                status="needs_clarification",
                query=test["query"],
                route=decision.route,
                filters=decision.filters,
                clarify_question=decision.clarify_question,
            )
        else:
            # For RAG routes, simulate successful response
            response = AnswerResponse(
                status="ok",
                query=test["query"],
                route=decision.route,
                filters=decision.filters,
                answer="Sample answer (would come from generate_answer)",
                sources=[{"doc_name": "sample.pdf", "org": "Sample", "page": 1}],
            )

        # Step 3: Verify response
        route_match = response.route == test["expected_route"]
        status_match = response.status == test["expected_status"]

        if route_match and status_match:
            print(f"  ✓ PASS - Route: {response.route}, Status: {response.status}")
            passed += 1
        else:
            print(f"  ✗ FAIL - Expected route: {test['expected_route']}, got: {response.route}")
            print(f"         Expected status: {test['expected_status']}, got: {response.status}")
            failed += 1

        # Show additional response details
        if response.clarify_question:
            print(f"  Clarification: {response.clarify_question}")
        if response.warning:
            print(f"  Warning: {response.warning}")

        # Verify group_by_org would be set correctly
        if decision.route in [Route.RAG_FILTERED, Route.RAG_ALL]:
            group_by_org = (decision.route == Route.RAG_ALL)
            print(f"  Would call generate_answer with group_by_org={group_by_org}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = test_router_to_response_flow()
    sys.exit(0 if success else 1)
