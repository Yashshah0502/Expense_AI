#!/usr/bin/env python3
"""
API Testing Script for /policy/answer endpoint
Tests all routing scenarios with real API calls
"""
import requests
import json
from typing import Optional


BASE_URL = "http://localhost:8000"


def test_endpoint(question: str, org: Optional[str] = None,
                 policy_type: Optional[str] = None,
                 doc_name: Optional[str] = None,
                 candidate_k: int = 30,
                 final_k: int = 5):
    """
    Test the /policy/answer endpoint with given parameters

    Args:
        question: The question to ask
        org: Optional organization filter
        policy_type: Optional policy type filter
        doc_name: Optional document name filter
        candidate_k: Number of candidates to retrieve
        final_k: Number of final results

    Returns:
        Response JSON or None if error
    """
    params = {
        "q": question,
        "candidate_k": candidate_k,
        "final_k": final_k
    }

    if org:
        params["org"] = org
    if policy_type:
        params["policy_type"] = policy_type
    if doc_name:
        params["doc_name"] = doc_name

    try:
        response = requests.post(f"{BASE_URL}/policy/answer", params=params, timeout=30)

        print(f"\n{'='*70}")
        print(f"Question: {question}")
        if org:
            print(f"Org Filter: {org}")
        if policy_type:
            print(f"Policy Type: {policy_type}")
        print(f"Status Code: {response.status_code}")
        print(f"{'='*70}")

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Status: {data['status']}")
            print(f"✓ Route: {data['route']}")
            print(f"✓ Filters: {json.dumps(data['filters'], indent=2)}")

            if data.get('answer'):
                print(f"\n📝 Answer:")
                print(f"{data['answer'][:500]}...")  # First 500 chars
                print(f"(Full answer length: {len(data['answer'])} characters)")

            if data.get('clarify_question'):
                print(f"\n❓ Clarification Needed:")
                print(f"{data['clarify_question']}")

            if data.get('warning'):
                print(f"\n  Warning:")
                print(f"{data['warning']}")

            if data.get('sources'):
                print(f"\nSources ({len(data['sources'])} found):")
                for i, source in enumerate(data['sources'][:3], 1):  # Show first 3
                    print(f"  {i}. [{source['org']}] {source['doc_name']} - Page {source['page']}")
                    print(f"     Score: {source.get('score', 'N/A')}")
                    print(f"     Snippet: {source['text_snippet'][:80]}...")
                if len(data['sources']) > 3:
                    print(f"  ... and {len(data['sources']) - 3} more sources")
            else:
                print(f"\nSources: None")

            return data
        else:
            print(f"Error: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


def main():
    """Run comprehensive API tests"""
    print("\n" + "="*70)
    print("🧪 TESTING /policy/answer ENDPOINT WITH ROUTER INTEGRATION")
    print("="*70)
    print("\nMake sure your FastAPI server is running:")
    print("  uvicorn main:app --reload")
    print("\nStarting tests in 3 seconds...")

    import time
    time.sleep(3)

    # Check if server is running
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        if health.status_code != 200:
            print("Server health check failed!")
            return
        print("✓ Server is healthy\n")
    except Exception as e:
        print(f"Cannot connect to server at {BASE_URL}")
        print(f"   Error: {e}")
        print("\nPlease start the server first:")
        print("  cd backend")
        print("  source .venv/bin/activate")
        print("  uvicorn main:app --reload")
        return

    tests_run = 0
    tests_passed = 0

    # Test 1: SQL Intent Detection
    print("\n" + "🔹"*35)
    print("TEST 1: SQL Intent Detection (Route: SQL_NOT_READY)")
    print("🔹"*35)
    result = test_endpoint("What is my expense status for report 123?")
    tests_run += 1
    if result and result['route'] == 'SQL_NOT_READY' and result['status'] == 'needs_sql':
        print("PASS: SQL intent correctly detected")
        tests_passed += 1
    else:
        print("FAIL: SQL intent not detected correctly")

    # Test 2: Clarification Needed
    print("\n" + "🔹"*35)
    print("TEST 2: Clarification Request (Route: CLARIFY)")
    print("🔹"*35)
    result = test_endpoint("Is business class allowed?")
    tests_run += 1
    if result and result['route'] == 'CLARIFY' and result['status'] == 'needs_clarification':
        print("PASS: Clarification correctly requested")
        tests_passed += 1
    else:
        print("FAIL: Clarification not requested correctly")

    # Test 3: Filtered Search (Org in Question)
    print("\n" + "🔹"*35)
    print("TEST 3: Filtered Search - Org in Question (Route: RAG_FILTERED)")
    print("🔹"*35)
    result = test_endpoint("For Stanford, is business class allowed?")
    tests_run += 1
    if result and result['route'] == 'RAG_FILTERED' and result['filters']['org'] == 'Stanford':
        print("PASS: Org correctly extracted and filtered")
        tests_passed += 1
    else:
        print("FAIL: Org filtering not working correctly")

    # Test 4: Filtered Search (Explicit Parameter)
    print("\n" + "🔹"*35)
    print("TEST 4: Filtered Search - Explicit Org Parameter (Route: RAG_FILTERED)")
    print("🔹"*35)
    result = test_endpoint("What is the travel policy?", org="Yale")
    tests_run += 1
    if result and result['route'] == 'RAG_FILTERED' and result['filters']['org'] == 'Yale':
        print("PASS: Explicit org parameter works")
        tests_passed += 1
    else:
        print("FAIL: Explicit org parameter not working")

    # Test 5: Multi-Org Comparison
    print("\n" + "🔹"*35)
    print("TEST 5: Multi-Org Comparison (Route: RAG_ALL)")
    print("🔹"*35)
    result = test_endpoint("Compare ASU vs Yale meal per diem")
    tests_run += 1
    if result and result['route'] == 'RAG_ALL' and result['filters']['org'] is None:
        print("PASS: Multi-org comparison detected")
        tests_passed += 1
    else:
        print("FAIL: Multi-org comparison not working")

    # Test 6: Policy Type Inference
    print("\n" + "🔹"*35)
    print("TEST 6: Policy Type Inference (Travel)")
    print("🔹"*35)
    result = test_endpoint("What is Michigan's flight booking policy?")
    tests_run += 1
    if result and result['filters']['policy_type'] == 'travel':
        print("PASS: Policy type correctly inferred")
        tests_passed += 1
    else:
        print("FAIL: Policy type inference not working")

    # Test 7: Policy Type Inference (Procurement)
    print("\n" + "🔹"*35)
    print("TEST 7: Policy Type Inference (Procurement)")
    print("🔹"*35)
    result = test_endpoint("What is Princeton's p-card policy?")
    tests_run += 1
    if result and result['filters']['policy_type'] == 'procurement':
        print("PASS: Procurement policy type inferred")
        tests_passed += 1
    else:
        print("FAIL: Procurement policy type not inferred")

    # Test 8: Parameter Override
    print("\n" + "🔹"*35)
    print("TEST 8: Explicit Parameters Override Inference")
    print("🔹"*35)
    result = test_endpoint(
        "Compare ASU vs Stanford",  # Would normally be RAG_ALL
        org="Columbia",  # But we override with explicit org
        policy_type="procurement"
    )
    tests_run += 1
    if (result and result['route'] == 'RAG_FILTERED' and
        result['filters']['org'] == 'Columbia' and
        result['filters']['policy_type'] == 'procurement'):
        print("PASS: Explicit parameters override inference")
        tests_passed += 1
    else:
        print("FAIL: Parameter override not working")

    # Test 9: candidate_k and final_k parameters
    print("\n" + "🔹"*35)
    print("TEST 9: Custom candidate_k and final_k Parameters")
    print("🔹"*35)
    result = test_endpoint(
        "What is Rutgers' travel policy?",
        candidate_k=50,
        final_k=10
    )
    tests_run += 1
    if result and result.get('sources') is not None:
        print("PASS: Custom k parameters accepted")
        tests_passed += 1
    else:
        print("FAIL: Custom k parameters not working")

    # Final Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {tests_run}")
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_run - tests_passed}")
    print(f"Success Rate: {(tests_passed/tests_run)*100:.1f}%")
    print("="*70)

    if tests_passed == tests_run:
        print("ALL TESTS PASSED! Router integration is working correctly.")
    else:
        print("  Some tests failed. Check the output above for details.")

    print("\n Next Steps:")
    print("  1. Review any failed tests above")
    print("  2. Test with your actual policy documents")
    print("  3. Visit http://localhost:8000/docs to test interactively")
    print("  4. Check TESTING_GUIDE.md for more test scenarios")


if __name__ == "__main__":
    main()
