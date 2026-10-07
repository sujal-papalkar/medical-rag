"""
Evaluator Orchestrator for RAG Retrieval.
Executes evaluation tests against the Golden Dataset using exact chunk_id matching,
measures all requested IR metrics, and prepares detailed comparison reports.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from .metrics import calculate_query_metrics, aggregate_metrics
from .retrieval_service import get_retrieval_service, RetrievalService

CURRENT_DIR = Path(__file__).resolve().parent
DATASET_PATH = CURRENT_DIR / "draft_golden_dataset.json"
DEFAULT_OUTPUT_PATH = CURRENT_DIR.parent / "retrieval_results" / "evaluation_report.json"


class RAGEvaluator:
    def __init__(self, dataset_path: Optional[Path] = None):
        self.dataset_path = dataset_path or DATASET_PATH
        self.retrieval_service: RetrievalService = get_retrieval_service()
        self.dataset = self.load_dataset()

    def load_dataset(self) -> Dict[str, Any]:
        """Loads the draft golden dataset from file."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found at: {self.dataset_path}")
        with self.dataset_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_test_case(
        self,
        test_case: Dict[str, Any],
        top_k: int = 10,
        pass_k_threshold: int = 5
    ) -> Dict[str, Any]:
        """
        Evaluates a single test case.
        - Retrieves top-k chunks using disease filter
        - Compares retrieved chunk_ids with relevant_chunk_ids
        - Computes Recall, Precision, Hit, MRR, F1
        - Annotates chunks and ground-truth comparison
        """
        question = test_case["question"]
        disease = test_case.get("disease")
        relevant_ids = test_case.get("relevant_chunk_ids", [])
        expected_pages = test_case.get("expected_pages", [])
        relevant_set = set(relevant_ids)

        retrieved_chunks = self.retrieval_service.retrieve(
            query=question,
            disease=disease,
            top_k=top_k
        )

        retrieved_ids = [c["chunk_id"] for c in retrieved_chunks]

        # Calculate exact IR metrics
        metrics = calculate_query_metrics(
            retrieved_chunk_ids=retrieved_ids,
            relevant_chunk_ids=relevant_ids,
            pass_k_threshold=pass_k_threshold
        )

        # Annotate retrieved chunks with ground-truth relevance
        annotated_retrieved = []
        for chunk in retrieved_chunks:
            chunk_copy = dict(chunk)
            is_match = chunk_copy["chunk_id"] in relevant_set
            chunk_copy["is_relevant"] = is_match
            chunk_copy["page_matches"] = chunk_copy.get("page") in expected_pages
            annotated_retrieved.append(chunk_copy)

        # Ground truth status summary
        ground_truth_status = []
        for g_id in relevant_ids:
            found_rank = None
            found_dist = None
            if g_id in retrieved_ids:
                found_rank = retrieved_ids.index(g_id) + 1
                found_dist = retrieved_chunks[found_rank - 1].get("distance")

            # Try to fetch snippet from cache or retrieved chunk
            cached_chunk = self.retrieval_service.get_chunk_by_id(g_id)
            snippet = cached_chunk.get("content", "")[:300] if cached_chunk else ""

            ground_truth_status.append({
                "chunk_id": g_id,
                "retrieved": found_rank is not None,
                "rank": found_rank,
                "distance": found_dist,
                "page": cached_chunk.get("page") if cached_chunk else None,
                "snippet": snippet
            })

        return {
            "test_id": test_case.get("test_id"),
            "title": test_case.get("title", ""),
            "disease": disease,
            "question": question,
            "relevant_chunk_ids": relevant_ids,
            "expected_pages": expected_pages,
            "document_name": test_case.get("document_name"),
            "section": test_case.get("section"),
            "verified": test_case.get("verified", False),
            "metrics": metrics,
            "ground_truth_status": ground_truth_status,
            "retrieved_chunks": annotated_retrieved,
            "total_retrieved": len(annotated_retrieved)
        }

    def evaluate_all(
        self,
        top_k: int = 10,
        disease_filter: Optional[str] = None,
        pass_k_threshold: int = 5
    ) -> Dict[str, Any]:
        """
        Runs evaluation on all test cases in the dataset (or filtered by disease).
        Returns comprehensive aggregate metrics and individual case evaluations.
        """
        cases = self.dataset.get("test_cases", [])
        if disease_filter:
            cases = [c for c in cases if c.get("disease") == disease_filter]

        results = []
        for case in cases:
            eval_res = self.evaluate_test_case(
                test_case=case,
                top_k=top_k,
                pass_k_threshold=pass_k_threshold
            )
            results.append(eval_res)

        aggregates = aggregate_metrics(results)

        report = {
            "metadata": {
                **self.dataset.get("metadata", {}),
                "evaluation_top_k": top_k,
                "pass_k_threshold": pass_k_threshold,
                "eval_timestamp": str(Path(__file__).stat().st_mtime)
            },
            "summary": aggregates,
            "case_results": results
        }

        return report

    def save_report(self, report: Dict[str, Any], output_path: Optional[Path] = None) -> Path:
        """Saves evaluation report to JSON file."""
        target = output_path or DEFAULT_OUTPUT_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return target
