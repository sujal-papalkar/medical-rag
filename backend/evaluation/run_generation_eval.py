"""
CLI Runner for Grounded Generation Evaluation (20 Scenarios, 10 Categories).
Executes all 20 test cases from generation_ground_truth_20_cases.json through the
retrieval + generation pipeline, evaluates all clinical metrics across 3 candidates,
selects the deterministic best candidate, saves generation_evaluation_report.json,
and prints a comprehensive category-wise and per-case summary.
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
ROOT_DIR = BACKEND_DIR.parent

for p in [str(ROOT_DIR), str(BACKEND_DIR), str(CURRENT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from evaluation.generation_evaluator import GenerationEvaluator, DEFAULT_REPORT_PATH, DATASET_PATH


def print_summary_table(report: dict):
    overall = report.get("overall_metrics") or report.get("summary", {})
    categories = report.get("category_metrics", {})
    cases = report.get("case_results", [])
    meta = report.get("metadata", {})

    print("\n" + "=" * 100)
    print("                     CLINICAL GENERATION EVALUATION REPORT (20 SCENARIOS)")
    print("=" * 100)
    print(f"Dataset:            {meta.get('dataset_name')} ({meta.get('total_cases', 20)} cases across {meta.get('total_categories', 10)} categories)")
    print(f"Total Answers:      {meta.get('total_cases', 20) * meta.get('candidates_per_case', 3)} answers evaluated (3 candidates per scenario)")
    print(f"Model Evaluated:    Gemini LLM via backend/generation.py")
    print(f"Top-K Reranked:     {meta.get('top_k', 5)} chunks")
    print(f"Execution Time:     {meta.get('total_duration_seconds', 0.0)} seconds (Avg Latency: {overall.get('average_latency_seconds', 'N/A')}s per case)")
    print(f"Status Counts:      Successful: {overall.get('successful_cases', 0)} | Quota Failures: {overall.get('quota_failures', 0)} | Failed: {overall.get('failed_generation_cases', 0)}")
    print("-" * 100)

    # Candidate pass rates
    print("CANDIDATE PASS RATES & BENCHMARKS:")
    print(f"  * Candidate 1 Pass Rate:         {overall.get('candidate_1_pass_rate', 'N/A')}%")
    print(f"  * Candidate 2 Pass Rate:         {overall.get('candidate_2_pass_rate', 'N/A')}%")
    print(f"  * Candidate 3 Pass Rate:         {overall.get('candidate_3_pass_rate', 'N/A')}%")
    print(f"  * BEST-CANDIDATE Pass Rate:      {overall.get('overall_pass_rate', overall.get('best_candidate_pass_rate', 'N/A'))}% ({overall.get('passed_cases')}/{overall.get('total_cases')} test cases passed)")
    print("-" * 100)

    # Overall quality metrics
    print("AGGREGATE GENERATION METRICS (ALL EVALUATED ANSWERS):")
    print(f"  * Clinical Completeness Score:   {overall.get('average_completeness', 0.0) * 100:.1f}% (Key Ground Truth Terms & Elements Recall)")
    print(f"  * Context Groundedness Score:    {overall.get('average_groundedness', 0.0) * 100:.1f}%")
    print(f"  * Context Faithfulness Score:    {overall.get('average_faithfulness', 0.0) * 100:.1f}%")
    print(f"  * Hallucination Rate:            {overall.get('hallucination_rate', 0.0)}% (0% is ideal)")
    print(f"  * Source Correctness Score:      {overall.get('average_source_correctness', 0.0) * 100:.1f}%")
    print(f"  * Clinical Context Match Score:  {overall.get('average_clinical_context_correctness', overall.get('average_clinical_context_score', 0.0)) * 100:.1f}%")
    print(f"  * Limitations Handling Score:    {overall.get('average_missing_information_handling', overall.get('average_missing_info_handling_score', 0.0)) * 100:.1f}%")
    print(f"  * Ground Truth Chunk Hit Rate:   {overall.get('chunk_hit_rate', 0.0)}%")
    print(f"  * Expected Page Match Rate:      {overall.get('page_match_rate', 0.0)}%")
    print("-" * 100)

    # Category-wise metrics
    print(f"{'Category':<35} | {'Cases':<5} | {'Passed':<6} | {'Pass Rate':<9} | {'Comp%':<6} | {'Ground%':<7} | {'Faith%':<6} | {'Halluc%':<7}")
    print("-" * 100)
    for cat_name, m in categories.items():
        pass_rate_str = f"{m.get('pass_rate', 0.0)}%"
        comp_str = f"{m.get('average_completeness', 0.0)*100:.1f}%"
        ground_str = f"{m.get('average_groundedness', 0.0)*100:.1f}%"
        faith_str = f"{m.get('average_faithfulness', 0.0)*100:.1f}%"
        halluc_str = f"{m.get('hallucination_rate', 0.0)}%"
        print(f"{cat_name[:35]:<35} | {m.get('count', 0):<5} | {m.get('passed_count', 0):<6} | {pass_rate_str:<9} | {comp_str:<6} | {ground_str:<7} | {faith_str:<6} | {halluc_str:<7}")
    print("-" * 100)

    # Individual case results
    print(f"{'Case ID':<12} | {'Category':<30} | {'Disease':<12} | {'Verdict':<8} | {'Best Cand':<9} | {'Comp%':<6} | {'Ground%':<7} | {'Status':<10}")
    print("-" * 100)
    for c in cases:
        cid = c.get("test_id", "")
        cat = c.get("category", "")[:30]
        dis = c.get("disease", "")[:12]
        verdict = c.get("verdict", "FAIL")
        best_cand = f"Cand #{c.get('best_candidate_id', 'N/A')}"
        best_eval = c.get("best_candidate_eval", {})
        comp = f"{best_eval.get('completeness_score', 0.0)*100:.0f}%"
        ground = f"{best_eval.get('groundedness_score', 0.0)*100:.0f}%"
        stat = c.get("generation_status", "unknown")
        print(f"{cid:<12} | {cat:<30} | {dis:<12} | {verdict:<8} | {best_cand:<9} | {comp:<6} | {ground:<7} | {stat:<10}")
    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(description="CLI Runner for Grounded Generation Evaluation (20 Scenarios)")
    parser.add_argument("--test-id", type=str, default=None, help="Filter to evaluate only one specific test case (e.g. TC-01-MP-01)")
    parser.add_argument("--category", type=str, default=None, help="Filter to evaluate only one specific category")
    parser.add_argument("--disease", type=str, default=None, help="Filter by disease (diabetes or respiratory_viral_infection)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieved chunks (default: 5)")
    parser.add_argument("--candidates", type=int, default=3, help="Number of candidates to generate per case (default: 3)")
    parser.add_argument("--out", type=str, default=None, help="Custom output report path")

    args = parser.parse_args()

    evaluator = GenerationEvaluator(
        dataset_path=DATASET_PATH,
        output_report_path=Path(args.out) if args.out else DEFAULT_REPORT_PATH
    )

    print("=" * 100)
    print("STARTING CLINICAL GENERATION EVALUATION BENCHMARK")
    print(f"Dataset path:      {DATASET_PATH.resolve()}")
    print(f"Report output:     {evaluator.output_report_path.resolve()}")
    print(f"Top-K Reranked:    {args.top_k}")
    print(f"Candidates / case: {args.candidates}")
    if args.test_id:
        print(f"Case Filter:       {args.test_id}")
    if args.category:
        print(f"Category Filter:   {args.category}")
    if args.disease:
        print(f"Disease Filter:    {args.disease}")
    print("=" * 100)

    report = evaluator.evaluate_all_cases(
        disease_filter=args.disease,
        category_filter=args.category,
        test_id_filter=args.test_id,
        top_k=args.top_k,
        num_candidates=args.candidates
    )

    evaluator.save_report(report)
    print_summary_table(report)
    print(f"\n[OK] Full evaluation report successfully saved to: {evaluator.output_report_path.resolve()}\n")


if __name__ == "__main__":
    main()
