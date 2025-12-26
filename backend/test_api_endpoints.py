"""
Test script for /policy/search and /policy/answer endpoints.
Tests filters, debug mode, and edge cases.
"""
import requests
import json
from typing import Optional

BASE_URL = "http://localhost:8000"

def test_search_no_filters():
    """Test basic search without filters"""
    print("\n=== Test 1: Basic search (no filters) ===")
    response = requests.get(
        f"{BASE_URL}/policy/search",
        params={"q": "lodging reimbursement", "final_k": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Results: {len(data.get('results', []))}")
    if data.get('results'):
        print(f"Top result: {data['results'][0].get('doc_name')} (score: {data['results'][0].get('rerank_score', 'N/A')})")
    return response.status_code == 200

def test_search_with_org_filter():
    """Test search with org filter"""
    print("\n=== Test 2: Search with org=Princeton ===")
    response = requests.get(
        f"{BASE_URL}/policy/search",
        params={"q": "lodging reimbursement", "org": "Princeton", "final_k": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Filters applied: {data.get('filters')}")
    print(f"Results: {len(data.get('results', []))}")

    # Verify all results match filter
    if data.get('results'):
        orgs = [r.get('org') for r in data['results']]
        print(f"Orgs in results: {set(orgs)}")
        all_princeton = all(org == 'PRINCETON' for org in orgs)
        print(f"All results from Princeton: {all_princeton}")
        return all_princeton
    return True

def test_search_with_policy_type_filter():
    """Test search with policy_type filter"""
    print("\n=== Test 3: Search with policy_type=travel ===")
    response = requests.get(
        f"{BASE_URL}/policy/search",
        params={"q": "flight upgrades", "policy_type": "travel", "final_k": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Filters applied: {data.get('filters')}")
    print(f"Results: {len(data.get('results', []))}")
    return response.status_code == 200

def test_search_debug_mode():
    """Test search with debug=true"""
    print("\n=== Test 4: Search with debug=true ===")
    response = requests.get(
        f"{BASE_URL}/policy/search",
        params={"q": "receipt requirements", "debug": True, "final_k": 3}
    )
    print(f"Status: {response.status_code}")
    data = response.json()

    if 'debug' in data:
        print(f"Debug info present: {data['debug']}")
        print(f"  - candidate_count: {data['debug'].get('candidate_count')}")
        print(f"  - keyword_count: {data['debug'].get('keyword_count')}")
        print(f"  - vector_count: {data['debug'].get('vector_count')}")
        return True
    return False

def test_search_no_results():
    """Test search with impossible filters (edge case)"""
    print("\n=== Test 5: Search with no results (edge case) ===")
    response = requests.get(
        f"{BASE_URL}/policy/search",
        params={"q": "lodging", "org": "NonExistentUniversity", "final_k": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Results: {len(data.get('results', []))}")
    print(f"Warning: {data.get('warning')}")

    has_warning = data.get('warning') is not None
    no_results = len(data.get('results', [])) == 0
    return has_warning and no_results

def test_answer_no_filters():
    """Test answer endpoint without filters"""
    print("\n=== Test 6: Answer generation (no filters) ===")
    response = requests.post(
        f"{BASE_URL}/policy/answer",
        params={"q": "What is the deadline for submitting expense reports?", "final_k": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Query: {data.get('query')}")
    print(f"Answer length: {len(data.get('answer', ''))}")
    print(f"Sources: {len(data.get('sources', []))}")
    if data.get('answer'):
        print(f"Answer preview: {data['answer'][:200]}...")
    if data.get('sources'):
        print(f"Top source: {data['sources'][0].get('doc_name')} (page {data['sources'][0].get('page')})")
    return len(data.get('answer', '')) > 0

def test_answer_with_org_filter():
    """Test answer endpoint with org filter"""
    print("\n=== Test 7: Answer with org=Yale ===")
    response = requests.post(
        f"{BASE_URL}/policy/answer",
        params={"q": "Can I upgrade my flight to business class?", "org": "Yale", "final_k": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Filters: {data.get('filters')}")
    print(f"Answer length: {len(data.get('answer', ''))}")
    print(f"Sources: {len(data.get('sources', []))}")

    # Verify all sources match filter
    if data.get('sources'):
        orgs = [s.get('org') for s in data['sources']]
        print(f"Orgs in sources: {set(orgs)}")
        all_yale = all(org == 'YALE' for org in orgs)
        print(f"All sources from Yale: {all_yale}")
        return all_yale
    return True

def test_answer_no_results():
    """Test answer endpoint with no results (edge case)"""
    print("\n=== Test 8: Answer with no results (edge case) ===")
    response = requests.post(
        f"{BASE_URL}/policy/answer",
        params={"q": "test query", "org": "FakeUniversity", "final_k": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Answer: '{data.get('answer')}'")
    print(f"Sources: {len(data.get('sources', []))}")
    print(f"Warning: {data.get('warning')}")

    has_warning = data.get('warning') is not None
    no_answer = len(data.get('answer', '')) == 0
    no_sources = len(data.get('sources', [])) == 0
    return has_warning and no_answer and no_sources

def test_answer_multiple_universities():
    """Test answer that should pull from multiple universities"""
    print("\n=== Test 9: Answer from multiple universities ===")
    response = requests.post(
        f"{BASE_URL}/policy/answer",
        params={"q": "Is a receipt required for all expenses?", "final_k": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Sources: {len(data.get('sources', []))}")

    if data.get('sources'):
        orgs = [s.get('org') for s in data['sources']]
        unique_orgs = set(orgs)
        print(f"Universities in sources: {unique_orgs}")
        print(f"Number of unique universities: {len(unique_orgs)}")

        for source in data['sources'][:3]:
            print(f"  - {source.get('org')}: {source.get('doc_name')} (page {source.get('page')})")

        return len(unique_orgs) > 1
    return False

def run_all_tests():
    """Run all tests and report results"""
    print("=" * 60)
    print("TESTING /policy/search and /policy/answer ENDPOINTS")
    print("=" * 60)

    tests = [
        ("Basic search (no filters)", test_search_no_filters),
        ("Search with org filter", test_search_with_org_filter),
        ("Search with policy_type filter", test_search_with_policy_type_filter),
        ("Search debug mode", test_search_debug_mode),
        ("Search no results edge case", test_search_no_results),
        ("Answer generation (no filters)", test_answer_no_filters),
        ("Answer with org filter", test_answer_with_org_filter),
        ("Answer no results edge case", test_answer_no_results),
        ("Answer from multiple universities", test_answer_multiple_universities),
    ]

    results = {}
    for name, test_func in tests:
        try:
            passed = test_func()
            results[name] = "PASS" if passed else "FAIL"
        except Exception as e:
            print(f"ERROR: {str(e)}")
            results[name] = "ERROR"

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    for name, result in results.items():
        status_symbol = "✓" if result == "PASS" else "✗"
        print(f"{status_symbol} {name}: {result}")

    passed = sum(1 for r in results.values() if r == "PASS")
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
