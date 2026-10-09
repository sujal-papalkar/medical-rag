"""
CLI Runner for Retrieval Evaluation Benchmark.

Usage:
    python backend/scripts/run_retrieval_eval.py [--top-k 5]
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator


def main():
    parser = argparse.ArgumentParser(description="Run RAG Retrieval Benchmark")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K cutoff (default: 5)")
    parser.add_argument("--dataset", type=str, default=None, help="Dataset JSON filename")
    parser.add_argument("--out", type=str, default=None, help="Output report path")
    args = parser.parse_args()

    dataset_path = Path(args.dataset) if args.dataset else (settings.DATASETS_PATH / "retrieval_golden_dataset.json")
    print("=" * 80)
    print("RAG RETRIEVAL BENCHMARK EVALUATION")
    print("=" * 80)
    print(f"Timestamp   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Dataset     : {dataset_path.name}")
    print(f"Top-K Cutoff: {args.top_k}")
    print("-" * 80)

    evaluator = RetrievalEvaluator(dataset_path=dataset_path)
    report = evaluator.evaluate_all(top_k=args.top_k)

    overall = report.get("overall_metrics", {})
    print("\nOVERALL BENCHMARK RESULTS:")
    for metric, val in overall.items():
        if isinstance(val, float):
            print(f"  * {metric.upper():<16}: {val:.4f}")
        else:
            print(f"  * {metric.upper():<16}: {val}")

    out_file = Path(args.out) if args.out else (settings.REPORTS_PATH / "retrieval_evaluation_report.json")
    evaluator.save_report(report, out_file)
    print(f"\nReport saved to: {out_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
