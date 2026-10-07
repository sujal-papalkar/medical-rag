"""
Metrics calculation module for RAG Retrieval Evaluation.
Implements exact, non-LLM information retrieval metrics:
- Recall@1, @3, @5, @10
- Precision@1, @3, @5, @10
- Hit@1, @3, @5, @10
- MRR (Mean Reciprocal Rank)
- F1@5 and F1@10
"""

from typing import List, Dict, Any, Set
from collections import defaultdict


K_VALUES = [1, 3, 5, 10]


def calculate_query_metrics(
    retrieved_chunk_ids: List[str],
    relevant_chunk_ids: List[str],
    pass_k_threshold: int = 5
) -> Dict[str, Any]:
    """
    Calculates IR metrics for a single query using exact chunk_id matching.

    Args:
        retrieved_chunk_ids: Ordered list of retrieved chunk IDs (ranked 1 to N).
        relevant_chunk_ids: Ground truth relevant chunk IDs.
        pass_k_threshold: The K value used for the primary Pass/Fail boolean (default: 5).

    Returns:
        Dict of computed metrics including Recall@k, Precision@k, Hit@k, MRR, F1@5, F1@10,
        plus first_relevant_rank and pass_status.
    """
    relevant_set: Set[str] = set(relevant_chunk_ids)
    total_relevant = len(relevant_set)

    if total_relevant == 0:
        raise ValueError("relevant_chunk_ids cannot be empty")

    metrics: Dict[str, Any] = {}

    # Reciprocal Rank (RR)
    first_relevant_rank = None
    for idx, cid in enumerate(retrieved_chunk_ids):
        if cid in relevant_set:
            first_relevant_rank = idx + 1
            break

    reciprocal_rank = 1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0
    metrics["mrr"] = round(reciprocal_rank, 4)
    metrics["first_relevant_rank"] = first_relevant_rank

    # Calculate metrics for each k in [1, 3, 5, 10]
    for k in K_VALUES:
        retrieved_at_k = retrieved_chunk_ids[:k]
        hits_at_k = [cid for cid in retrieved_at_k if cid in relevant_set]
        num_hits = len(hits_at_k)

        # Hit@k (Binary: 1 if at least one relevant retrieved, else 0)
        hit_at_k = 1.0 if num_hits > 0 else 0.0
        metrics[f"hit@{k}"] = hit_at_k

        # Precision@k (hits / k)
        precision_at_k = num_hits / float(k)
        metrics[f"precision@{k}"] = round(precision_at_k, 4)

        # Recall@k (hits / total_relevant)
        recall_at_k = num_hits / float(total_relevant)
        metrics[f"recall@{k}"] = round(recall_at_k, 4)

    # F1@5 and F1@10
    for k in [5, 10]:
        p = metrics[f"precision@{k}"]
        r = metrics[f"recall@{k}"]
        if (p + r) > 0:
            f1 = (2 * p * r) / (p + r)
        else:
            f1 = 0.0
        metrics[f"f1@{k}"] = round(f1, 4)

    # Pass / Fail status: Hit within top-k threshold
    is_passed = metrics.get(f"hit@{pass_k_threshold}", 0.0) == 1.0
    metrics["pass"] = is_passed
    metrics["pass_criteria"] = f"Hit@{pass_k_threshold} == 1"

    return metrics


def aggregate_metrics(case_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregates metrics across multiple evaluation cases:
    Computes macro averages for overall dataset and per-disease breakdowns.
    """
    if not case_results:
        return {}

    metric_keys = [
        "hit@1", "hit@3", "hit@5", "hit@10",
        "precision@1", "precision@3", "precision@5", "precision@10",
        "recall@1", "recall@3", "recall@5", "recall@10",
        "mrr", "f1@5", "f1@10"
    ]

    def average_metrics(results_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        count = len(results_list)
        if count == 0:
            return {}

        avg: Dict[str, Any] = {
            "count": count,
            "passed_count": sum(1 for r in results_list if r.get("metrics", {}).get("pass", False)),
            "failed_count": sum(1 for r in results_list if not r.get("metrics", {}).get("pass", False)),
        }
        avg["pass_rate"] = round(avg["passed_count"] / float(count), 4)

        for key in metric_keys:
            total_val = sum(r.get("metrics", {}).get(key, 0.0) for r in results_list)
            avg[key] = round(total_val / float(count), 4)

        return avg

    overall = average_metrics(case_results)

    # Group by disease
    by_disease = defaultdict(list)
    for res in case_results:
        disease = res.get("disease", "unknown")
        by_disease[disease].append(res)

    disease_aggregates = {
        disease: average_metrics(items)
        for disease, items in by_disease.items()
    }

    return {
        "overall": overall,
        "by_disease": disease_aggregates,
        "total_test_cases": len(case_results),
    }
