"""
Retrieval Benchmark Evaluator.

Orchestrates evaluation over retrieval datasets, computing exact IR metrics:
Recall@K, Precision@K, Hit@K, MRR, and F1 scores.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.rag.retrieval import get_retrieval_service, RetrievalService
from evaluation.metrics import calculate_query_metrics, aggregate_metrics

DEFAULT_DATASET = settings.DATASETS_PATH / "retrieval_golden_dataset.json"
DEFAULT_REPORT_PATH = settings.REPORTS_PATH / "retrieval_evaluation_report.json"


class RetrievalEvaluator:
    """Evaluates candidate retrieval and reranking performance."""

    def __init__(self, dataset_path: Optional[Path] = None):
        self.dataset_path = dataset_path or DEFAULT_DATASET
        self.retrieval_service: RetrievalService = get_retrieval_service()
        self.dataset = self.load_dataset()

    def load_dataset(self) -> Dict[str, Any]:
        """Loads dataset from JSON file."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found at: {self.dataset_path}")
        with self.dataset_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_test_case(
        self,
        test_case: Dict[str, Any],
        top_k: int = 5,
        pass_k_threshold: int = 5
    ) -> Dict[str, Any]:
        """Evaluates a single scenario."""
        question = test_case.get("query") or test_case.get("question", "")
        disease = test_case.get("disease")
        relevant_ids = test_case.get("relevant_chunk_ids") or test_case.get("expected_chunk_ids", [])
        expected_pages = test_case.get("expected_pages", [])
        relevant_set = set(relevant_ids)

        retrieved = self.retrieval_service.retrieve(
            query=question,
            disease=disease,
            top_k=top_k
        )
        retrieved_ids = [c["chunk_id"] for c in retrieved]

        metrics = None
        if relevant_ids:
            metrics = calculate_query_metrics(
                retrieved_chunk_ids=retrieved_ids,
                relevant_chunk_ids=relevant_ids,
                pass_k_threshold=pass_k_threshold
            )

        annotated = []
        for c in retrieved:
            c_dict = dict(c)
            c_dict["is_relevant"] = c_dict["chunk_id"] in relevant_set if relevant_set else None
            annotated.append(c_dict)

        return {
            "test_id": test_case.get("scenario_id") or test_case.get("test_id"),
            "category": test_case.get("category"),
            "query": question,
            "disease": disease,
            "relevant_chunk_ids": relevant_ids,
            "metrics": metrics,
            "retrieved_chunks": annotated
        }

    def evaluate_all(self, top_k: int = 5) -> Dict[str, Any]:
        """Runs evaluation over all scenarios in the dataset."""
        if isinstance(self.dataset, list):
            cases = self.dataset
        else:
            cases = self.dataset.get("scenarios") or self.dataset.get("test_cases", [])
        case_results = []
        for c in cases:
            res = self.evaluate_test_case(c, top_k=top_k)
            case_results.append(res)

        overall = aggregate_metrics(case_results)

        report = {
            "metadata": {
                "dataset": str(self.dataset_path.name),
                "total_cases": len(cases),
                "top_k": top_k
            },
            "overall_metrics": overall,
            "case_results": case_results
        }
        return report

    def save_report(self, report: Dict[str, Any], output_path: Optional[Path] = None):
        out = output_path or DEFAULT_REPORT_PATH
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
