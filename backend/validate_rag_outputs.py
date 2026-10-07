from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path

def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[*_`>#\[\]|]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--chunks", required=True)
    p.add_argument("--markdown-dir")
    p.add_argument("--out", default="validation_report.txt")
    p.add_argument("--json-out", default="validation_report.json")
    p.add_argument("--min-chars", type=int, default=300)
    p.add_argument("--max-chars", type=int, default=1800)
    a = p.parse_args()

    data = json.loads(Path(a.chunks).read_text(encoding="utf-8"))
    chunks = data.get("chunks", data) if isinstance(data, dict) else data

    errors, warnings, reviews, infos = [], [], [], []

    for c in chunks:
        n = len(c.get("content", ""))
        if n > a.max_chars:
            errors.append(f"{c.get('chunk_id')}: oversized chunk ({n})")

        if 0 < n < a.min_chars:
            t = c.get("content_type")
            if t == "title":
                infos.append(f"{c.get('chunk_id')}: short title retained as structure")
            elif t == "table":
                infos.append(f"{c.get('chunk_id')}: short table fragment retained as structure")
            else:
                warnings.append(f"{c.get('chunk_id')}: short fragment ({n} chars): {c.get('content')!r}")

    # Do not flag duplicate tables: repeated headers/rows are expected when
    # tables are split across chunks.
    seen = defaultdict(list)
    for c in chunks:
        if c.get("content_type") == "table":
            continue
        key = (c.get("document_id"), c.get("content_type"), norm(c.get("content")))
        if key[2]:
            seen[key].append(c.get("chunk_id"))
    for (_, _, _), ids in seen.items():
        if len(ids) > 1:
            warnings.append(f"{ids[0]}: duplicate normalized content appears {len(ids)} times (same document/content type)")

    by_doc = defaultdict(list)
    for c in chunks:
        by_doc[c.get("document_id")].append(c)

    for _, items in by_doc.items():
        for left, right in zip(items, items[1:]):
            x = (left.get("content") or "").rstrip()
            y = (right.get("content") or "").lstrip()
            if (
                left.get("content_type") not in {"table", "title"}
                and right.get("content_type") not in {"table", "title"}
                and y and y[0].islower()
                and x and not re.search(r"[.!?।:;]$", x)
            ):
                reviews.append(f"{left.get('chunk_id')}: likely mid-sentence split before {right.get('chunk_id')}")

    types = Counter(c.get("content_type", "unknown") for c in chunks)
    diseases = Counter(c.get("disease", "unknown") for c in chunks)
    pages = sum(c.get("page") is not None for c in chunks)
    missing_page_chunks = [c.get("chunk_id") for c in chunks if c.get("page") is None]
    invalid_page_chunks = [
        c.get("chunk_id") for c in chunks
        if c.get("page") is not None and (not isinstance(c.get("page"), int) or c.get("page") < 1)
    ]
    for chunk_id in missing_page_chunks:
        errors.append(f"{chunk_id}: missing page provenance")
    for chunk_id in invalid_page_chunks:
        errors.append(f"{chunk_id}: invalid page provenance")

    report = [
        f"Total chunks: {len(chunks)}",
        f"Issues: ERROR={len(errors)} | WARNING={len(warnings)} | REVIEW={len(reviews)} | INFO={len(infos)}",
        "",
        "CONTENT TYPES",
        *[f"- {k}: {v}" for k, v in sorted(types.items())],
        "",
        "DISEASES",
        *[f"- {k}: {v}" for k, v in sorted(diseases.items())],
        "",
        "ERRORS",
        *([f"- {x}" for x in errors] or ["- None"]),
        "",
        "WARNINGS",
        *([f"- {x}" for x in warnings] or ["- None"]),
        "",
        "REVIEW",
        *([f"- {x}" for x in reviews] or ["- None"]),
        "",
        "INFO",
        *[f"- {x}" for x in infos],
    ]
    if pages == 0:
        report.append("- Page provenance is unavailable in all chunks; add page numbers during Docling extraction.")

    text = "\n".join(report)
    print(text)
    Path(a.out).write_text(text, encoding="utf-8")
    Path(a.json_out).write_text(json.dumps({
        "total_chunks": len(chunks),
        "errors": errors, "warnings": warnings, "reviews": reviews,
        "infos": infos,
        "page_provenance_chunks": pages,
        "missing_page_chunks": missing_page_chunks,
        "invalid_page_chunks": invalid_page_chunks,
        "content_types": dict(types), "diseases": dict(diseases)
    }, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
