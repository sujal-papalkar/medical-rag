"""
Clinical RAG Retrieval Scenarios Test Runner.

Executes test scenarios defined in retrieval_scenarios.json against the
existing evaluation/retrieval_service.py without modifying existing pipeline code.

For each query, retrieves Top-5 results and prints:
- Query
- Rank
- Chunk ID
- Page
- Section
- Distance
- Content preview
- Whether an expected chunk/section was retrieved
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================
# RESOLVE PATHS & IMPORT RETRIEVAL SERVICE
# ============================================================

CURRENT_DIR = Path(__file__).resolve().parent

# Check if parent is backend directory or root
if (CURRENT_DIR.parent / "evaluation" / "retrieval_service.py").exists():
    BACKEND_DIR = CURRENT_DIR.parent
elif (CURRENT_DIR.parent / "backend" / "evaluation" / "retrieval_service.py").exists():
    BACKEND_DIR = CURRENT_DIR.parent / "backend"
elif (CURRENT_DIR / "evaluation" / "retrieval_service.py").exists():
    BACKEND_DIR = CURRENT_DIR
else:
    BACKEND_DIR = CURRENT_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from evaluation.retrieval_service import get_retrieval_service
except ImportError as e:
    raise ImportError(
        f"Failed to import get_retrieval_service from evaluation.retrieval_service. "
        f"Backend directory: {BACKEND_DIR}. Error: {e}"
    )

SCENARIOS_FILE = CURRENT_DIR / "retrieval_scenarios.json"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_content_preview(content: str, max_chars: int = 150) -> str:
    """Clean whitespace and truncate text for console display."""
    if not content:
        return "(empty)"
    # Replace multiple spaces and newlines with a single space
    cleaned = " ".join(content.split())
    if len(cleaned) > max_chars:
        return cleaned[:max_chars].rstrip() + "..."
    return cleaned


def normalize_str(s: Optional[str]) -> str:
    """Normalize string for robust section name comparison."""
    if not s:
        return ""
    return " ".join(s.strip().lower().split())


def load_scenarios(file_path: Path) -> List[Dict[str, Any]]:
    """Load test scenarios from JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Scenarios file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("scenarios", [])


# ============================================================
# EVALUATION METRICS
# ============================================================

def calculate_metrics(
    retrieved_chunk_ids: List[str],
    relevant_chunk_ids: List[str],
    top_k: int,
) -> Dict[str, float]:
    """Calculate Precision@K, Recall@K, F1@K and Reciprocal Rank.

    Supports multiple relevant chunks correctly.
    """
    relevant_set = set(relevant_chunk_ids or [])
    retrieved_at_k = retrieved_chunk_ids[:top_k]
    hits = [cid for cid in retrieved_at_k if cid in relevant_set]
    num_hits = len(hits)

    precision = num_hits / top_k if top_k > 0 else 0.0
    recall = num_hits / len(relevant_set) if relevant_set else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    reciprocal_rank = 0.0
    for rank, cid in enumerate(retrieved_chunk_ids, start=1):
        if cid in relevant_set:
            reciprocal_rank = 1.0 / rank
            break

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "reciprocal_rank": reciprocal_rank,
        "hits": float(num_hits),
        "total_relevant": float(len(relevant_set)),
    }


# ============================================================
# MAIN TEST EXECUTION
# ============================================================

def run_retrieval_scenarios(
    top_k: int = 5,
    filter_category: Optional[str] = None,
    filter_test_id: Optional[str] = None
) -> None:
    # Ensure stdout handles UTF-8 characters cleanly on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    scenarios = load_scenarios(SCENARIOS_FILE)
    service = get_retrieval_service()

    if filter_category:
        scenarios = [
            s for s in scenarios
            if s.get("category", "").lower() == filter_category.lower()
        ]
    if filter_test_id:
        scenarios = [
            s for s in scenarios
            if s.get("test_id", "").lower() == filter_test_id.lower()
        ]

    print("=" * 80)
    print("CLINICAL RAG RETRIEVAL SCENARIOS BENCHMARK")
    print("=" * 80)
    print(f"Total Scenarios to Evaluate : {len(scenarios)}")
    print(f"Retrieval Depth (Top-K)    : {top_k}")
    print(f"Scenarios Source            : {SCENARIOS_FILE}")
    print("=" * 80)

    summary_rows = []

    for index, sc in enumerate(scenarios, start=1):
        test_id = sc.get("test_id", f"TC-{index:03d}")
        category = sc.get("category", "General")
        disease = sc.get("disease", "")
        query = sc.get("query", "")

        # Support both plural list and singular field formats
        expected_chunk_ids = sc.get("expected_chunk_ids") or []
        if not expected_chunk_ids and sc.get("expected_chunk_id"):
            expected_chunk_ids = [sc["expected_chunk_id"]]

        expected_sections = sc.get("expected_sections") or []
        if not expected_sections and sc.get("expected_section"):
            expected_sections = [sc["expected_section"]]

        expected_pages = sc.get("expected_pages") or []
        if not expected_pages and sc.get("expected_page") is not None:
            expected_pages = [sc["expected_page"]]

        print(f"\n{'-' * 80}")
        print(f"TEST CASE [{index}/{len(scenarios)}]: {test_id}")
        print(f"Category           : {category}")
        print(f"Disease Target     : {disease}")
        print(f"Expected Chunk(s)  : {', '.join(expected_chunk_ids) if expected_chunk_ids else 'None specified'}")
        print(f"Expected Page(s)   : {expected_pages}")
        print(f"Expected Section(s): {expected_sections}")
        print(f"Query              : {query}")
        print(f"{'-' * 80}")

        # Execute retrieval via existing retrieval service
        results = service.retrieve(
            query=query,
            disease=disease if disease else None,
            top_k=top_k
        )

        chunk_hit = False
        section_hit = False
        target_rank = None
        target_section_rank = None
        retrieved_chunk_ids = []
        matched_chunk_ids = []

        norm_expected_sections = [normalize_str(sec) for sec in expected_sections]

        print(f"\nRetrieved Top-{len(results)} Results:")
        print(f"{'Rank':<5} | {'Chunk ID':<35} | {'Page':<5} | {'Distance':<8} | {'Section'}")
        print("." * 80)

        for res in results:
            rank = res.get("rank")
            cid = res.get("chunk_id", "")
            page = res.get("page", "N/A")
            distance = res.get("distance", "N/A")
            section = res.get("section", "")
            content = res.get("content", "")

            retrieved_chunk_ids.append(cid)

            # Check matches
            is_chunk_match = cid in expected_chunk_ids
            is_sec_match = normalize_str(section) in norm_expected_sections

            if is_chunk_match:
                chunk_hit = True
                matched_chunk_ids.append(cid)
                if target_rank is None:
                    target_rank = rank

            if is_sec_match and not section_hit:
                section_hit = True
                target_section_rank = rank

            match_marker = []
            if is_chunk_match:
                match_marker.append("MATCH: CHUNK")
            if is_sec_match:
                match_marker.append("MATCH: SECTION")
            marker_str = f" <<< {' & '.join(match_marker)} >>>" if match_marker else ""

            print(f"{rank:<5} | {cid:<35} | {str(page):<5} | {str(distance):<8} | {section[:50]}{marker_str}")
            print(f"      Preview: {format_content_preview(content)}")

        print("\nRetrieval Evaluation Summary:")
        if chunk_hit:
            print(f"  [PASS] Expected Chunk(s) Retrieved : {len(matched_chunk_ids)}/{len(expected_chunk_ids)} (first at Rank #{target_rank})")
        else:
            print(f"  [FAIL] Expected Chunk(s) Retrieved : 0/{len(expected_chunk_ids)} (not found in top-{top_k})")

        if section_hit:
            print(f"  [PASS] Expected Section Retrieved : YES (at Rank #{target_section_rank})")
        else:
            print(f"  [INFO] Expected Section Retrieved : NO")

        metrics = calculate_metrics(
            retrieved_chunk_ids=retrieved_chunk_ids,
            relevant_chunk_ids=expected_chunk_ids,
            top_k=top_k,
        )

        summary_rows.append({
            "test_id": test_id,
            "category": category,
            "disease": disease,
            "target_rank": target_rank,
            "chunk_hit": chunk_hit,
            "section_hit": section_hit,
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "reciprocal_rank": metrics["reciprocal_rank"],
            "hits": int(metrics["hits"]),
            "total_relevant": int(metrics["total_relevant"]),
        })

    # ========================================================
    # FINAL SUMMARY REPORT
    # ========================================================
    print("\n" + "=" * 80)
    print("FINAL BENCHMARK SUMMARY REPORT")
    print("=" * 80)
    print(
        f"{'Test ID':<13} | {'Category':<35} | {'Rank':<6} | "
        f"{'Chunk Hit':<10} | {'Section Hit':<11} | "
        f"{'Prec@'+str(top_k):<8} | {'Rec@'+str(top_k):<8} | "
        f"{'F1@'+str(top_k):<8} | {'Hits':<6} | {'RR':<6}"
    )
    print("-" * 125)

    for row in summary_rows:
        rank_display = (
            f"#{row['target_rank']}"
            if row["target_rank"]
            else "-"
        )
        chunk_hit_str = "YES" if row["chunk_hit"] else "NO"
        sec_hit_str = "YES" if row["section_hit"] else "NO"

        print(
            f"{row['test_id']:<13} | "
            f"{row['category'][:35]:<35} | "
            f"{rank_display:<6} | "
            f"{chunk_hit_str:<10} | "
            f"{sec_hit_str:<11} | "
            f"{row['precision']:<8.4f} | "
            f"{row['recall']:<8.4f} | "
            f"{row['f1']:<8.4f} | "
            f"{row['hits']}/{row['total_relevant']:<4} | "
            f"{row['reciprocal_rank']:<6.4f}"
        )

    total_cases = len(summary_rows)
    total_chunk_hits = sum(
        1 for r in summary_rows
        if r["chunk_hit"]
    )
    total_sec_hits = sum(
        1 for r in summary_rows
        if r["section_hit"]
    )

    precision_at_k = (
        sum(r["precision"] for r in summary_rows)
        / max(total_cases, 1)
    )

    recall_at_k = (
        sum(r["recall"] for r in summary_rows)
        / max(total_cases, 1)
    )

    f1_at_k = (
        sum(r["f1"] for r in summary_rows)
        / max(total_cases, 1)
    )

    mrr = (
        sum(r["reciprocal_rank"] for r in summary_rows)
        / max(total_cases, 1)
    )

    pass_rate = (
        total_chunk_hits / max(total_cases, 1)
    ) * 100.0

    section_pass_rate = (
        total_sec_hits / max(total_cases, 1)
    ) * 100.0

    print("=" * 125)
    print(f"Total Test Cases Evaluated : {total_cases}")
    print(
        f"Chunk Hit@{top_k} Pass Count   : "
        f"{total_chunk_hits} / {total_cases} "
        f"({pass_rate:.1f}%)"
    )
    print(
        f"Section Hit@{top_k} Count     : "
        f"{total_sec_hits} / {total_cases} "
        f"({section_pass_rate:.1f}%)"
    )
    print(
        f"Precision@{top_k}              : "
        f"{precision_at_k:.4f}"
    )
    print(
        f"Recall@{top_k}                 : "
        f"{recall_at_k:.4f}"
    )
    print(
        f"F1@{top_k}                     : "
        f"{f1_at_k:.4f}"
    )
    print(
        f"Mean Reciprocal Rank (MRR)     : "
        f"{mrr:.4f}"
    )
    print("=" * 125)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run clinical retrieval scenario tests against RetrievalService"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of top candidates to retrieve per query (default: 5)"
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter and run tests for a specific category"
    )
    parser.add_argument(
        "--test-id",
        type=str,
        default=None,
        help="Filter and run a single test case by ID"
    )

    args = parser.parse_args()

    run_retrieval_scenarios(
        top_k=args.top_k,
        filter_category=args.category,
        filter_test_id=args.test_id
    )
