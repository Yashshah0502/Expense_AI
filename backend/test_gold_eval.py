"""
Test the API endpoints against the gold.jsonl evaluation dataset.
Checks both search and answer quality.
"""
import requests
import json
from typing import List, Dict

BASE_URL = "http://localhost:8000"

def load_gold_dataset(file_path: str) -> List[Dict]:
    """Load the gold evaluation dataset"""
    with open(file_path, 'r') as f:
        return [json.loads(line) for line in f]

def extract_doc_id(doc_ref: str) -> tuple:
    """Extract doc name and page from reference like 'ASU.pdf_34'"""
    parts = doc_ref.rsplit('_', 1)
    if len(parts) == 2:
        return parts[0], int(parts[1])
    return parts[0], None

def test_search_recall(queries: List[Dict], k: int = 5) -> Dict:
    """Test Recall@K for search endpoint"""
    print(f"\n{'='*60}")
    print(f"EVALUATING SEARCH RECALL@{k}")
    print(f"{'='*60}\n")

    total_recall = 0
    total_mrr = 0
    num_queries = len(queries)

    for i, item in enumerate(queries, 1):
        query = item['query']
        relevant_docs = item['relevant_docs']

        # Call search endpoint
        response = requests.get(
            f"{BASE_URL}/policy/search",
            params={"q": query, "final_k": k}
        )

        if response.status_code != 200:
            print(f"[{i}/{num_queries}] ERROR: Query failed - {query[:50]}...")
            continue

        data = response.json()
        results = data.get('results', [])

        # Calculate recall
        retrieved_ids = set()
        for r in results:
            doc_name = r.get('doc_name', '')
            chunk_index = r.get('chunk_index')
            doc_id = f"{doc_name}_{chunk_index}"
            retrieved_ids.add(doc_id)

        relevant_ids = set(relevant_docs)
        hits = len(retrieved_ids & relevant_ids)
        recall = hits / len(relevant_ids) if relevant_ids else 0
        total_recall += recall

        # Calculate MRR (Mean Reciprocal Rank)
        mrr = 0
        for rank, r in enumerate(results, 1):
            doc_name = r.get('doc_name', '')
            chunk_index = r.get('chunk_index')
            doc_id = f"{doc_name}_{chunk_index}"
            if doc_id in relevant_ids:
                mrr = 1.0 / rank
                break
        total_mrr += mrr

        status = "✓" if recall == 1.0 else "○" if recall > 0 else "✗"
        print(f"[{i:2d}/{num_queries}] {status} Recall: {recall:.2f} | MRR: {mrr:.3f} | {query[:60]}")

    avg_recall = total_recall / num_queries if num_queries > 0 else 0
    avg_mrr = total_mrr / num_queries if num_queries > 0 else 0

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Average Recall@{k}: {avg_recall:.4f}")
    print(f"  Average MRR: {avg_mrr:.4f}")
    print(f"{'='*60}\n")

    return {
        "avg_recall": avg_recall,
        "avg_mrr": avg_mrr,
        "num_queries": num_queries
    }

def test_answer_quality(queries: List[Dict], sample_size: int = 5) -> None:
    """Test a sample of answer generation quality"""
    print(f"\n{'='*60}")
    print(f"SAMPLE ANSWER QUALITY CHECK ({sample_size} queries)")
    print(f"{'='*60}\n")

    for i, item in enumerate(queries[:sample_size], 1):
        query = item['query']

        # Call answer endpoint
        response = requests.post(
            f"{BASE_URL}/policy/answer",
            params={"q": query, "final_k": 5}
        )

        if response.status_code != 200:
            print(f"[{i}] ERROR: Query failed - {query}")
            continue

        data = response.json()
        answer = data.get('answer', '')
        sources = data.get('sources', [])

        print(f"[Query {i}]")
        print(f"Q: {query}")
        print(f"A: {answer[:200]}{'...' if len(answer) > 200 else ''}")
        print(f"Sources: {len(sources)} documents from {len(set(s['org'] for s in sources))} universities")
        if sources:
            print(f"  Top source: {sources[0]['org']} - {sources[0]['doc_name']} (page {sources[0]['page']})")
        print()

def test_filtered_searches() -> None:
    """Test filter functionality with specific queries"""
    print(f"\n{'='*60}")
    print("TESTING FILTER FUNCTIONALITY")
    print(f"{'='*60}\n")

    test_cases = [
        {
            "query": "What is the deadline for submitting expense reports?",
            "filters": {"org": "Princeton"},
            "expected_org": "PRINCETON"
        },
        {
            "query": "Can I upgrade my flight to business class?",
            "filters": {"policy_type": "travel"},
            "expected_has_results": True
        },
        {
            "query": "lodging reimbursement",
            "filters": {"org": "Yale", "policy_type": "travel"},
            "expected_org": "YALE"
        }
    ]

    for i, test in enumerate(test_cases, 1):
        query = test['query']
        filters = test['filters']

        params = {"q": query, "final_k": 5}
        params.update(filters)

        response = requests.get(
            f"{BASE_URL}/policy/search",
            params=params
        )

        data = response.json()
        results = data.get('results', [])

        print(f"[Test {i}] Query: {query[:50]}")
        print(f"  Filters: {filters}")
        print(f"  Results: {len(results)}")

        if 'expected_org' in test and results:
            orgs = set(r['org'] for r in results)
            matches = all(org == test['expected_org'] for org in orgs)
            status = "✓" if matches else "✗"
            print(f"  {status} Org filter: {orgs} (expected {test['expected_org']})")
        elif 'expected_has_results' in test:
            status = "✓" if (len(results) > 0) == test['expected_has_results'] else "✗"
            print(f"  {status} Has results: {len(results) > 0}")

        print()

def run_evaluation():
    """Run complete evaluation suite"""
    # Load gold dataset
    gold_data = load_gold_dataset('eval/gold.jsonl')
    print(f"Loaded {len(gold_data)} queries from gold.jsonl")

    # Test 1: Search Recall
    recall_results = test_search_recall(gold_data, k=5)

    # Test 2: Answer Quality Sample
    test_answer_quality(gold_data, sample_size=5)

    # Test 3: Filter Functionality
    test_filtered_searches()

    # Final summary
    print(f"\n{'='*60}")
    print("EVALUATION COMPLETE")
    print(f"{'='*60}")
    print(f"Recall@5: {recall_results['avg_recall']:.4f}")
    print(f"MRR: {recall_results['avg_mrr']:.4f}")
    print(f"Total queries evaluated: {recall_results['num_queries']}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    run_evaluation()
