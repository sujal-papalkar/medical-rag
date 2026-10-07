"""
Command-line runner for RAG Retrieval Evaluation.
Runs all 10 test cases in draft_golden_dataset.json and outputs a formatted
table of metrics and saves the evaluation report.

Usage:
    python backend/evaluation/run_eval.py [--top-k 10] [--pass-k 5]
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.evaluator import RAGEvaluator


def format_table_row(cols, widths):
    formatted = []
    for c, w in zip(cols, widths):
        formatted.append(str(c).ljust(w)[:w])
    return " | ".join(formatted)


def main():
    parser = argparse.ArgumentParser(description="Run RAG Retrieval Evaluation on Draft Golden Dataset")
    parser.add_argument("--top-k", type=int, default=10, help="Number of retrieved chunks (default: 10)")
    parser.add_argument("--pass-k", type=int, default=5, help="Cutoff K for Pass/Fail determination (default: 5)")
    parser.add_argument("--disease", type=str, default=None, help="Filter by disease (diabetes or respiratory_viral_infection)")
    parser.add_argument("--out", type=str, default=None, help="Custom output JSON path")

    args = parser.parse_args()

    print("=" * 100)
    print("RAG RETRIEVAL EVALUATION - PHASE 1: DISEASE-SPECIFIC BENCHMARK")
    print("=" * 100)
    print(f"Timestamp        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Top-K Cutoff     : {args.top_k}")
    print(f"Pass Criterion   : Hit@{args.pass_k} == 1.0")
    if args.disease:
        print(f"Disease Filter   : {args.disease}")
    print("=" * 100)

    evaluator = RAGEvaluator()
    dataset_meta = evaluator.dataset.get("metadata", {})
    print(f"Dataset Status   : [{dataset_meta.get('status', 'DRAFT')}] - {dataset_meta.get('description')}")
    print(f"Total Cases      : {len(evaluator.dataset.get('test_cases', []))}")
    print("-" * 100)
    print("Running evaluation against ChromaDB using existing disease-specific retrieval...\n")

    report = evaluator.evaluate_all(
        top_k=args.top_k,
        disease_filter=args.disease,
        pass_k_threshold=args.pass_k
    )

    out_path = evaluator.save_report(
        report=report,
        output_path=Path(args.out) if args.out else None
    )

    # Print individual test cases
    headers = ["Test ID", "Disease", "Pass?", "First Rank", "Hit@1", "Hit@3", "Hit@5", "Hit@10", "Rec@5", "Rec@10", "F1@5", "MRR"]
    widths = [11, 26, 6, 10, 6, 6, 6, 6, 6, 6, 6, 6]

    print(format_table_row(headers, widths))
    print("-" * 105)

    for item in report["case_results"]:
        m = item["metrics"]
        pass_str = "PASS" if m.get("pass") else "FAIL"
        first_r = str(m.get("first_relevant_rank") or "N/A")
        cols = [
            item["test_id"],
            item["disease"],
            pass_str,
            first_r,
            f"{m['hit@1']:.0f}",
            f"{m['hit@3']:.0f}",
            f"{m['hit@5']:.0f}",
            f"{m['hit@10']:.0f}",
            f"{m['recall@5']:.2f}",
            f"{m['recall@10']:.2f}",
            f"{m['f1@5']:.2f}",
            f"{m['mrr']:.3f}"
        ]
        print(format_table_row(cols, widths))

    print("-" * 105)

    # Print Summary Aggregates
    summary = report["summary"]
    overall = summary.get("overall", {})

    print("\n" + "=" * 55)
    print("AGGREGATE METRICS SUMMARY (MACRO AVERAGE)")
    print("=" * 55)
    print(f"Total Evaluated  : {overall.get('count')}")
    print(f"Passed Cases     : {overall.get('passed_count')} ({overall.get('pass_rate', 0)*100:.1f}%)")
    print(f"Failed Cases     : {overall.get('failed_count')}")
    print(f"Mean Reciprocal Rank (MRR) : {overall.get('mrr', 0):.4f}")
    print("-" * 55)
    print(f"Hit@1   : {overall.get('hit@1', 0)*100:5.1f}% | Hit@3   : {overall.get('hit@3', 0)*100:5.1f}% | Hit@5   : {overall.get('hit@5', 0)*100:5.1f}% | Hit@10   : {overall.get('hit@10', 0)*100:5.1f}%")
    print(f"Rec@1   : {overall.get('recall@1', 0)*100:5.1f}% | Rec@3   : {overall.get('recall@3', 0)*100:5.1f}% | Rec@5   : {overall.get('recall@5', 0)*100:5.1f}% | Rec@10   : {overall.get('recall@10', 0)*100:5.1f}%")
    print(f"Prec@1  : {overall.get('precision@1', 0)*100:5.1f}% | Prec@3  : {overall.get('precision@3', 0)*100:5.1f}% | Prec@5  : {overall.get('precision@5', 0)*100:5.1f}% | Prec@10  : {overall.get('precision@10', 0)*100:5.1f}%")
    print(f"F1@5    : {overall.get('f1@5', 0):.4f} | F1@10   : {overall.get('f1@10', 0):.4f}")

    print("\n" + "=" * 55)
    print("DISEASE BREAKDOWN COMPARISON")
    print("=" * 55)
    by_disease = summary.get("by_disease", {})
    for dis, stats in by_disease.items():
        print(f"\n[Disease: {dis.upper()}] (n={stats.get('count')}, Pass: {stats.get('passed_count')}/{stats.get('count')})")
        print(f"  MRR       : {stats.get('mrr'):.4f}")
        print(f"  Hit@1/3/5 : {stats.get('hit@1')*100:.0f}% / {stats.get('hit@3')*100:.0f}% / {stats.get('hit@5')*100:.0f}%")
        print(f"  Recall@5  : {stats.get('recall@5')*100:.1f}% | Recall@10: {stats.get('recall@10')*100:.1f}%")
        print(f"  F1@5      : {stats.get('f1@5'):.4f} | F1@10   : {stats.get('f1@10'):.4f}")

    print("\n" + "=" * 100)
    print(f"Complete detailed report saved to: {out_path.resolve()}")
    print("=" * 100)


if __name__ == "__main__":
    main()
