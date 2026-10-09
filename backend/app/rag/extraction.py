#!/usr/bin/env python3
"""Extract PDF/DOCX files with Docling while preserving inspectable structure.

Run from the project backend folder:
    python test_docling.py

Input:  sample_documents/
Output: output/
    <name>.md            Human-readable Markdown export
    <name>.json          Full Docling document export
    <name>.html          HTML export (if supported by installed Docling)
    <name>.tables.json   Tables exported separately for auditing
    extraction_summary.json
"""
from __future__ import annotations

import json
import logging
import re
import sys
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter

from app.core.config import settings

INPUT_DIR = settings.UPLOADS_PATH
OUTPUT_DIR = settings.EXTRACTED_PATH
SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("docling-extraction")


def json_safe(value: Any) -> Any:
    """Convert common Docling/Python values into JSON-serializable values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return json_safe(value.model_dump(mode="json"))
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return json_safe(value.dict())
        except Exception:
            pass
    return str(value)


def get_page_numbers(item: Any) -> list[int]:
    """Best-effort page provenance extraction; missing provenance stays empty."""
    pages: set[int] = set()
    provenance = getattr(item, "prov", None) or []
    for prov in provenance:
        page_no = getattr(prov, "page_no", None)
        if page_no is None and isinstance(prov, dict):
            page_no = prov.get("page_no")
        if page_no is not None:
            try:
                pages.add(int(page_no))
            except (TypeError, ValueError):
                pass
    return sorted(pages)


def _item_text(item: Any) -> str:
    """Return the main textual representation of a Docling item."""
    text = getattr(item, "text", None)
    if text:
        return str(text).strip()

    # Some Docling item types expose text through export_to_text().
    export_to_text = getattr(item, "export_to_text", None)
    if callable(export_to_text):
        try:
            exported = export_to_text()
            if exported:
                return str(exported).strip()
        except Exception:
            pass

    return ""


def _item_label(item: Any) -> str:
    """Return a stable Docling item type name."""
    return type(item).__name__


def export_page_provenance(document: Any) -> dict[str, Any]:
    """
    Build a sidecar provenance map from Docling document items.

    The normal Markdown export does not reliably retain page boundaries.
    This sidecar keeps the original Markdown untouched while recording
    which source page(s) each extracted item came from.
    """
    items: list[dict[str, Any]] = []

    # iterate_items is the preferred Docling API for document order.
    iterator = getattr(document, "iterate_items", None)
    if callable(iterator):
        try:
            iterable = iterator()
            for entry in iterable:
                # Docling versions commonly return (item, level) tuples
                # from iterate_items(). Unwrap the actual document item.
                item = entry[0] if isinstance(entry, tuple) and entry else entry

                pages = get_page_numbers(item)
                text = _item_text(item)
                items.append({
                    "item_type": _item_label(item),
                    "text": text,
                    "page_numbers": pages,
                })
        except Exception:
            items = []

    # Fallback for versions where iterate_items is unavailable.
    if not items:
        for collection_name in ("texts", "tables", "pictures"):
            collection = getattr(document, collection_name, None) or []
            for item in collection:
                pages = get_page_numbers(item)
                text = _item_text(item)
                items.append({
                    "item_type": _item_label(item),
                    "text": text,
                    "page_numbers": pages,
                })

    page_numbers = sorted({
        page
        for item in items
        for page in item.get("page_numbers", [])
    })

    return {
        "page_count_observed": len(page_numbers),
        "page_numbers_observed": page_numbers,
        "items": items,
        "note": (
            "Page provenance is taken from Docling item.prov.page_no. "
            "The normal Markdown export is intentionally unchanged; "
            "use this sidecar to map extracted content back to source pages."
        ),
    }


def inject_page_markers(markdown: str, provenance: dict[str, Any]) -> str:
    """
    Add lightweight page markers to Markdown when a reliable text match exists.

    This is intentionally conservative: if a marker cannot be mapped reliably,
    the original Markdown text is retained rather than inventing page numbers.
    """
    items = provenance.get("items", [])
    page_for_text: dict[str, int] = {}

    for item in items:
        text = str(item.get("text") or "").strip()
        pages = item.get("page_numbers") or []
        if text and pages:
            # Only map reasonably distinctive text blocks.
            normalized = re.sub(r"\s+", " ", text)
            if len(normalized) >= 20:
                page_for_text[normalized] = int(pages[0])

    if not page_for_text:
        return markdown

    lines = markdown.splitlines()
    output: list[str] = []
    current_page: int | None = None

    # Match distinctive extracted item text against the Markdown stream.
    # We do not alter the source text itself.
    for line in lines:
        normalized_line = re.sub(r"\s+", " ", line.strip())
        if normalized_line:
            matched_page = None
            for item_text, page in page_for_text.items():
                # Exact line match or a sufficiently distinctive prefix.
                if normalized_line == item_text or (
                    len(normalized_line) >= 30
                    and (
                        item_text.startswith(normalized_line)
                        or normalized_line.startswith(item_text)
                    )
                ):
                    matched_page = page
                    break

            if matched_page is not None and matched_page != current_page:
                output.append(f"<!-- PAGE: {matched_page} -->")
                current_page = matched_page

        output.append(line)

    return "\n".join(output)


def table_to_record(table: Any, document: Any, index: int) -> dict[str, Any]:
    """Export a table in multiple forms so cell structure can be inspected."""
    record: dict[str, Any] = {
        "table_index": index,
        "page_numbers": get_page_numbers(table),
        "markdown": None,
        "html": None,
        "rows": [],
        "row_count": None,
        "column_count": None,
        "extraction_method": None,
        "warnings": [],
    }

    try:
        record["markdown"] = table.export_to_markdown(document)
    except Exception as exc:
        record["warnings"].append(f"Markdown export failed: {type(exc).__name__}: {exc}")

    try:
        record["html"] = table.export_to_html(document)
    except Exception as exc:
        # Some Docling versions do not expose export_to_html on table objects.
        record["warnings"].append(f"Table HTML export unavailable: {type(exc).__name__}: {exc}")

    # Preferred structured route: Docling's table-to-dataframe exporter.
    try:
        dataframe = table.export_to_dataframe(doc=document)
        dataframe = dataframe.fillna("")
        record["rows"] = [
            {"cells": [str(value) for value in row]}
            for row in dataframe.astype(str).values.tolist()
        ]
        record["column_headers"] = [str(column) for column in dataframe.columns.tolist()]
        record["row_count"] = len(record["rows"])
        record["column_count"] = len(record["column_headers"])
        record["extraction_method"] = "docling_dataframe"
    except Exception as exc:
        record["warnings"].append(
            f"DataFrame export unavailable; trying table cells: {type(exc).__name__}: {exc}"
        )

    # Fallback: retain cell text and row/column offsets. This does not guess merged-cell values.
    if not record["rows"]:
        data = getattr(table, "data", None)
        cells = getattr(data, "table_cells", None) or []
        if cells:
            normalized_cells = []
            max_row = -1
            max_col = -1
            for cell in cells:
                text = getattr(cell, "text", "")
                row_start = getattr(cell, "start_row_offset_idx", None)
                row_end = getattr(cell, "end_row_offset_idx", None)
                col_start = getattr(cell, "start_col_offset_idx", None)
                col_end = getattr(cell, "end_col_offset_idx", None)
                normalized_cells.append({
                    "text": str(text or ""),
                    "row_start": row_start,
                    "row_end": row_end,
                    "col_start": col_start,
                    "col_end": col_end,
                    "column_header": bool(getattr(cell, "column_header", False)),
                    "row_header": bool(getattr(cell, "row_header", False)),
                })
                for value in (row_start, row_end):
                    if isinstance(value, int):
                        max_row = max(max_row, value)
                for value in (col_start, col_end):
                    if isinstance(value, int):
                        max_col = max(max_col, value)
            record["cells"] = normalized_cells
            record["row_count"] = max_row + 1 if max_row >= 0 else None
            record["column_count"] = max_col + 1 if max_col >= 0 else None
            record["extraction_method"] = "docling_table_cells"
        else:
            record["warnings"].append("No structured cell data exposed by this Docling version.")

    if record["markdown"]:
        # A lightweight warning only; it does not claim extraction is incorrect.
        pipe_lines = [line for line in record["markdown"].splitlines() if "|" in line]
        if len(pipe_lines) >= 2:
            widths = [line.count("|") for line in pipe_lines]
            if len(set(widths)) > 1:
                record["warnings"].append(
                    "Markdown table lines have different pipe counts; inspect possible merged cells or formatting."
                )
    return record


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(json_safe(data), ensure_ascii=False, indent=2), encoding="utf-8")


def find_libreoffice() -> str | None:
    """Find LibreOffice without requiring it to be on PATH."""
    configured = os.environ.get("DOCLING_LIBREOFFICE_CMD")
    if configured:
        candidate = Path(configured.strip('"'))
        if candidate.exists():
            return str(candidate)
        resolved = shutil.which(configured)
        if resolved:
            return resolved

    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    return shutil.which("soffice")


def convert_docx_to_pdf(docx_path: Path) -> Path:
    """Render DOCX to PDF so Docling can attach reliable physical page provenance."""
    pdf_path = OUTPUT_DIR / f"{docx_path.stem}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        logger.info("  Using existing rendered PDF: %s", pdf_path.name)
        return pdf_path

    soffice = find_libreoffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice was not found. Install LibreOffice or set "
            "DOCLING_LIBREOFFICE_CMD to the full path of soffice.exe."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        soffice,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(OUTPUT_DIR.resolve()),
        str(docx_path.resolve()),
    ]
    logger.info("  Rendering DOCX with LibreOffice: %s", soffice)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("LibreOffice timed out while converting DOCX to PDF.") from exc

    if completed.stdout.strip():
        logger.info("  LibreOffice: %s", completed.stdout.strip().replace("\n", " | "))
    if completed.stderr.strip():
        logger.warning("  LibreOffice stderr: %s", completed.stderr.strip().replace("\n", " | "))

    if completed.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(
            f"LibreOffice failed to convert {docx_path.name} to PDF "
            f"(returncode={completed.returncode})."
        )

    logger.info("  Rendered PDF: %s", pdf_path)
    return pdf_path


def main() -> int:
    if not INPUT_DIR.exists():
        logger.error("Input folder does not exist: %s", INPUT_DIR.resolve())
        logger.error("Create sample_documents/ and place PDF/DOCX files inside it.")
        return 1

    files = sorted(
        path for path in INPUT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        logger.error("No PDF or DOCX files found in %s", INPUT_DIR.resolve())
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    converter = DocumentConverter()
    summary: list[dict[str, Any]] = []

    for file_path in files:
        logger.info("Processing %s", file_path.name)
        base_name = file_path.stem
        item_summary: dict[str, Any] = {
            "source_file": file_path.name,
            "status": "failed",
            "table_count": 0,
            "markdown_chars": 0,
            "warnings": [],
        }
        try:
            # DOCX physical page numbers are renderer-dependent. Render DOCX
            # to a fixed-layout PDF first, then let Docling extract page
            # provenance from the PDF via item.prov.page_no.
            source_for_docling = file_path
            if file_path.suffix.lower() == ".docx":
                source_for_docling = convert_docx_to_pdf(file_path)
                item_summary["rendered_pdf"] = source_for_docling.name

            result = converter.convert(str(source_for_docling))
            document = result.document

            markdown = document.export_to_markdown()
            md_path = OUTPUT_DIR / f"{base_name}.md"
            md_path.write_text(markdown, encoding="utf-8")

            raw_json = document.export_to_dict()
            json_path = OUTPUT_DIR / f"{base_name}.json"
            write_json(json_path, raw_json)

            # Build explicit page provenance from Docling's item-level prov data.
            provenance = export_page_provenance(document)
            provenance_path = OUTPUT_DIR / f"{base_name}.provenance.json"
            write_json(provenance_path, {
                "source_file": file_path.name,
                "docling_source": source_for_docling.name,
                **provenance,
            })

            # Add conservative page markers to Markdown where an extracted
            # item can be matched reliably. Unmatched content is left intact.
            markdown_with_pages = inject_page_markers(markdown, provenance)
            if markdown_with_pages != markdown:
                md_path.write_text(markdown_with_pages, encoding="utf-8")
                markdown = markdown_with_pages

            try:
                html = document.export_to_html()
                (OUTPUT_DIR / f"{base_name}.html").write_text(html, encoding="utf-8")
            except Exception as exc:
                item_summary["warnings"].append(
                    f"Document HTML export unavailable: {type(exc).__name__}: {exc}"
                )

            tables = list(getattr(document, "tables", []) or [])
            table_records = [
                table_to_record(table, document, index)
                for index, table in enumerate(tables, start=1)
            ]
            tables_path = OUTPUT_DIR / f"{base_name}.tables.json"
            write_json(tables_path, {
                "source_file": file_path.name,
                "table_count": len(table_records),
                "tables": table_records,
            })

            item_summary.update({
                "status": "success",
                "table_count": len(table_records),
                "markdown_chars": len(markdown),
                "json_file": json_path.name,
                "markdown_file": md_path.name,
                "tables_file": tables_path.name,
                "provenance_file": provenance_path.name,
                "page_count_observed": provenance.get("page_count_observed", 0),
                "page_numbers_observed": provenance.get("page_numbers_observed", []),
            })
            for table in table_records:
                if table.get("warnings"):
                    item_summary["warnings"].append(
                        f"Table {table['table_index']}: " + "; ".join(table["warnings"])
                    )

            logger.info("  Markdown: %s (%s chars)", md_path.name, len(markdown))
            logger.info("  Structured JSON: %s", json_path.name)
            logger.info(
                "  Provenance: %s (pages=%s)",
                provenance_path.name,
                provenance.get("page_numbers_observed", []),
            )
            logger.info("  Tables: %s -> %s", len(table_records), tables_path.name)
            for table in table_records:
                dimensions = f"{table.get('row_count')} rows x {table.get('column_count')} columns"
                logger.info("    Table %s: %s; method=%s",
                            table["table_index"], dimensions, table.get("extraction_method"))
                for warning in table.get("warnings", []):
                    logger.warning("    Table %s: %s", table["table_index"], warning)

        except Exception as exc:
            item_summary["error"] = f"{type(exc).__name__}: {exc}"
            logger.exception("Failed to process %s", file_path.name)

        summary.append(item_summary)

    summary_path = OUTPUT_DIR / "extraction_summary.json"
    write_json(summary_path, {
        "input_dir": str(INPUT_DIR),
        "output_dir": str(OUTPUT_DIR),
        "document_count": len(summary),
        "successful_documents": sum(1 for item in summary if item["status"] == "success"),
        "failed_documents": sum(1 for item in summary if item["status"] != "success"),
        "documents": summary,
        "note": "DOCX files are rendered to fixed-layout PDF with LibreOffice before Docling extraction so physical page provenance can be captured from item.prov.page_no. Extraction warnings still require visual comparison with the source.",
    })
    logger.info("Summary saved: %s", summary_path)
    return 0 if all(item["status"] == "success" for item in summary) else 2


if __name__ == "__main__":
    raise SystemExit(main())
