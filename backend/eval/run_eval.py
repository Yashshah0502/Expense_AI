import json
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from rag.policy_search import hybrid_search
from dotenv import load_dotenv

load_dotenv()

GOLD_FILE = Path(__file__).parent / "gold.jsonl"

def load_gold_set(file_path):
    data = []
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def run_evaluation():
    if not GOLD_FILE.exists():
        print(f"Gold file not found at {GOLD_FILE}")
        return

    gold_data = load_gold_set(GOLD_FILE)
    print(f"Loaded {len(gold_data)} eval examples.")

    total_recall = 0.0
    total_mrr = 0.0
    count = 0

    # Top K to evaluate (e.g. FINAL_K=5)
    K = 5

    for example in gold_data:
        query = example["query"]
        relevant_keys = set(example["relevant_docs"]) # e.g. {"ASU.pdf_0", "ASU.pdf_1"}

        if not relevant_keys:
            continue

        try:
            # Call hybrid search
            # hybrid_search returns {"query": q, "results": [...]}
            # results have doc_name, chunk_index
            response = hybrid_search(query, top_k=K)
            results = response["results"]
        except Exception as e:
            print(f"Error querying '{query}': {e}")
            continue

        # Calculate metrics for this query
        recall_hit = 0
        reciprocal_rank = 0.0

        print(f"Query: {query}")
        print(f"  Relevant: {relevant_keys}")
        
        found_at_rank = None
        
        for rank, r in enumerate(results, start=1):
            # Construct key from result
            res_key = f"{r['doc_name']}_{r['chunk_index']}"
            print(f"    {rank}. {res_key} (Score: {r.get('rerank_score')})")

            if res_key in relevant_keys:
                recall_hit = 1
                if reciprocal_rank == 0.0:
                    reciprocal_rank = 1.0 / rank
                    found_at_rank = rank
        
        total_recall += recall_hit
        total_mrr += reciprocal_rank
        count += 1
        
        print(f"  -> Recall@{K}: {recall_hit}, RR: {reciprocal_rank:.4f}, First Match: {found_at_rank}\n")

    if count > 0:
        avg_recall = total_recall / count
        avg_mrr = total_mrr / count
        print("--------------------------------------------------")
        print(f"Evaluation Results (N={count}, K={K}):")
        print(f"Average Recall@{K}: {avg_recall:.4f}")
        print(f"Mean Reciprocal Rank (MRR): {avg_mrr:.4f}")
        print("--------------------------------------------------")
    else:
        print("No valid examples run.")

if __name__ == "__main__":
    run_evaluation()
