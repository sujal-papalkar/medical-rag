"""
CLI Runner for Grounded Generation Evaluation (20 Scenarios, 10 Categories).
"""

import sys
import argparse
from pathlib import Path

# Ensure utf-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from evaluation.evaluators.generation_evaluator import GenerationEvaluator

DEFAULT_DATASET = settings.DATASETS_PATH / "generation_ground_truth.json"
DEFAULT_REPORT = settings.REPORTS_PATH / "generation_evaluation_report.json"


def main():
    parser = argparse.ArgumentParser(description="Run 20-Scenario Generation Evaluation")
    parser.add_argument("--top-k", type=int, default=5, help="Evidence chunks to retrieve (default: 5)")
    parser.add_argument("--candidates", type=int, default=3, help="Candidates to evaluate per scenario (default: 3)")
    parser.add_argument("--out", type=str, default=str(DEFAULT_REPORT), help="Output JSON report path")
    args = parser.parse_args()

    print("=" * 80)
    print("CLINICAL GENERATION EVALUATION RUNNER")
    print("=" * 80)
    print(f"Ground Truth Dataset: {DEFAULT_DATASET.name}")
    print(f"Candidates Per Case : {args.candidates}")
    print(f"Top-K Reranked Chunks: {args.top_k}")
    print("-" * 80)

    evaluator = GenerationEvaluator(dataset_path=DEFAULT_DATASET)
    report = evaluator.evaluate_all(top_k=args.top_k, candidates_per_case=args.candidates)
    evaluator.save_report(report, Path(args.out))
    print(f"\nReport saved to: {args.out}")
    print("=" * 80)


if __name__ == "__main__":
    main()
