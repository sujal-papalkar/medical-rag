"""
Generic, structure-aware chunker for Docling/Markdown/JSON extracted documents.

Goals:
- Generic across heterogeneous medical guideline documents.
- Target chunk size: <= TARGET_CHARS whenever possible.
- Preserve headings, prose, lists and tables.
- Split large Markdown tables by rows.
- Never allow a long table-row fragment to push a chunk over TARGET_CHARS.
- Merge small extraction fragments into useful neighboring context.
- Remove exact repeated extraction boilerplate conservatively.
- Exclude placeholder/image-only artifacts from embedding.
- Preserve page provenance when page markers exist in the extracted source.
- Produce one JSON file per document plus chunks.json and chunk_summary.json.

This file is intended to replace the existing chunking.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TARGET_CHARS = 1800
MIN_CHUNK_CHARS = 300
SHORT_FRAGMENT_CHARS = 260
MAX_DEDUP_CHARS = 700

# Keep this mapping explicit for the current documents. Add new document stems
# here as new disease-specific source documents are introduced.
DISEASE_BY_DOCUMENT = {
    "DM RR": "diabetes",
    "Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1)": "respiratory_viral_infection",
}

PLACEHOLDER_PATTERNS = [
    re.compile(r"^\s*<!--\s*(?:image|figure|picture|graphic)(?:\s*:[^>]*)?\s*-->\s*$", re.I),
    re.compile(r"^\s*\[?\s*(?:image|figure|picture|graphic)\s*(?:placeholder)?\s*\]?\s*$", re.I),
    re.compile(r"^\s*<image[^>]*>\s*$", re.I),
]

PAGE_PATTERNS = [
    re.compile(r"\[Document:[^\]]*?,\s*Page:\s*(\d+)\]", re.I),
    re.compile(r"\[Page:\s*(\d+)\]", re.I),
    re.compile(r"<!--\s*page(?:-number)?\s*:\s*(\d+)\s*-->", re.I),
    re.compile(r"^\s*Page\s+(\d+)\s+of\s+\d+\s*$", re.I),
]

HEADING_WORDS = {
    "abstract", "aim", "aims", "assessment", "background", "conclusion",
    "contraindications", "diagnosis", "diet", "discussion", "dosage",
    "dose", "guidelines", "high risk", "indication", "indications",
    "investigation", "investigations", "management", "medicine",
    "matra", "aushadh", "aushadh kal", "objective", "objectives",
    "precautions", "prophylactic", "prophylaxis", "recommendation",
    "recommendations", "references", "ref", "results", "symptoms",
    "therapeutic", "therapy", "treatment", "upadrav", "viral infection",
    "during sansarga", "sansarga", "post respiratory viral infection",
    "terminology", "protocol", "index", "patient", "patients",
}

SIGNATURE_PATTERNS = [
    re.compile(r"thank(?:ing)?\s+you", re.I),
    re.compile(r"vd\.?\s*yogesh\s+bendale", re.I),
    re.compile(r"dr\.?\s*yogesh\s+bendale", re.I),
    re.compile(r"cmd,\s*ayurveda\s+rasayani", re.I),
]

DISCLAIMER_PATTERNS = [
    re.compile(r"only for the guidance of registered ayurvedic medical practitioners", re.I),
    re.compile(r"only for use by (?:the )?registered ayurvedic medical practitioners", re.I),
    re.compile(r"contributors will not be held responsible in any way for the same", re.I),
    re.compile(r"diseases mentioned in bracket are only for the purpose of general understanding", re.I),
    re.compile(r"it should not be considered as mere translation of ayurvedic terminology", re.I),
    re.compile(r"considered as mere translation of ayurvedic terminology\)?", re.I),
    re.compile(r"^\s*##?\s*disclaimer\s*$", re.I),
    re.compile(r"^\s*disclaimer\s*$", re.I),
    re.compile(r"^\s*asayani\s*$", re.I),
]

MAJOR_SECTION_PATTERNS = [
    re.compile(r"^\s*PROPHYLACTIC GUIDELINES\s*$", re.I),
    re.compile(r"^\s*PROPHYLACTIC GUIDELINES FOR HIGH[- ]RISK PATIENTS\b", re.I),
    re.compile(r"^\s*THERAPEUTIC GUIDELINES\s*$", re.I),
    re.compile(r"^\s*PRAMEH\s*\(DIABETES MELLITUS\)\s*MANAGEMENT\b", re.I),
    re.compile(r"^\s*TREATMENT GUIDELINES FOR THE MANAGEMENT OF PRAMEH UPADRAV\b", re.I),
    re.compile(r"^\s*HELPS IN SECONDARY PREVENTION\b", re.I),
    re.compile(r"^\s*INVESTIGATION PROTOCOL\b", re.I),
    re.compile(r"^\s*GUIDELINES FOR MANAGEMENT OF SPECIFIC SYMPTOMS\b", re.I),
    re.compile(r"^\s*UPADRAV\s*\(POST VIRAL\b", re.I),
    re.compile(r"^\s*THERAPEUTIC INDEX\b", re.I),
    re.compile(r"^\s*OTHER DETAILS/INSTRUCTIONS\b", re.I),
]

SUB_SUBSECTION_PATTERNS = [
    re.compile(r"^\s*Pranvah Srotas vyadhi \((?:Below|Above)\s*\d+\s*Years\)", re.I),
    re.compile(r"^\s*Raktavah Srotas\b", re.I),
    re.compile(r"^\s*Basic Guidelines to reduce disease severity\b", re.I),
    re.compile(r"^\s*i\.e\., HELPS TO PREVENT THE ONSET\b", re.I),
    re.compile(r"^\s*(?:Annavah|Mootravah|Manovah|Udakvah|Rasavah|Rasvah|Pranvah)\s+Srotas\b", re.I),
    re.compile(r"^\s*Patients with\s+(?:Pranvah|Rasavah|Udakvah|Mootravah|Annavah|Manovah|Raktavah|Hrudrog|Prameh)\b", re.I),
]

DOC_TITLE_PATTERNS = [
    re.compile(r"^\s*Guidelines for the Management of\b", re.I),
]

IGNORE_HEADING_PATTERNS = [
    re.compile(r"^\s*DISCLAIMER\s*$", re.I),
    re.compile(r"^\s*asayani\s*$", re.I),
    re.compile(r"^\s*Dear Vaidyas[,.]?\s*$", re.I),
]

BOILERPLATE_EXACT = {
    "during sansarga (infection)",
}

BOILERPLATE_HINTS = (
    "only for the guidance of registered ayurvedic medical practitioners",
    "only for use by the registered ayurvedic medical practitioners",
    "contributors will not be held responsible in any way for the same",
    "diseases mentioned in bracket",
)

def is_signature(text: str) -> bool:
    norm = normalized_for_dedupe(text)
    return any(p.search(norm) for p in SIGNATURE_PATTERNS)

def is_disclaimer_boilerplate(text: str) -> bool:
    norm = normalized_for_dedupe(text)
    if not norm:
        return False
    for pattern in DISCLAIMER_PATTERNS:
        if pattern.search(norm):
            if len(norm) < 400:
                return True
    return False

def is_ocr_garbage(text: str) -> bool:
    s = text.strip()
    if len(s) <= 2 and not s.isalnum():
        return True
    if len(s) == 1 and ord(s) > 127:  # Non-ASCII single characters, e.g. OCR artifact '\u65e5'
        return True
    return False

def clean_heading(text: str) -> str:
    s = re.sub(r"^#{1,6}\s*", "", text).strip()
    s = re.sub(r"\s*<!--.*?-->\s*", "", s).strip()
    return normalize_text(s)

def format_section_context(
    section: Optional[str],
    subsection: Optional[str],
    sub_subsection: Optional[str] = None,
    comorbidity: Optional[str] = None
) -> str:
    lines = []
    if section:
        lines.append(f"Section: {section}")
    if subsection and subsection != section:
        lines.append(f"Subsection: {subsection}")
    if sub_subsection and sub_subsection not in (section, subsection):
        lines.append(f"Sub-subsection: {sub_subsection}")
    if comorbidity and comorbidity not in (section, subsection, sub_subsection):
        lines.append(f"Comorbidity: {comorbidity}")
    if lines:
        return "\n".join(lines) + "\n\n"
    return ""

def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def normalized_for_dedupe(text: str) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"[*_`>#\[\]]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def stable_id(document_id: str, index: int, content: str) -> str:
    digest = hashlib.sha1(
        f"{document_id}|{index}|{content}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"{document_id}-{index:04d}-{digest}"

def document_id_for(path: Path) -> str:
    digest = hashlib.sha1(path.stem.encode("utf-8")).hexdigest()[:12].upper()
    return f"DOC-{digest}"

def is_placeholder_line(line: str) -> bool:
    return any(p.search(line) for p in PLACEHOLDER_PATTERNS)

def is_placeholder_only(text: str) -> bool:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    return bool(lines) and all(is_placeholder_line(x) for x in lines)

def strip_placeholder_lines(text: str) -> str:
    kept = [line for line in text.splitlines() if not is_placeholder_line(line)]
    return normalize_text("\n".join(kept))

def extract_page(text: str) -> Optional[int]:
    for pattern in PAGE_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
    return None

def clean_page_markers(text: str) -> str:
    for pattern in PAGE_PATTERNS:
        text = pattern.sub("", text)
    return normalize_text(text)

def split_blocks(source: str) -> List[Dict[str, Any]]:
    """
    Split Markdown into structural blocks while retaining table blocks and
    propagating page provenance from standalone page markers.

    Page markers such as:
        <!-- PAGE: 7 -->
        [Page: 7]
        [Document: ..., Page: 7]

    are treated as source-position state rather than retrieval content. Every
    following block inherits the current page until another page marker is
    encountered.
    """
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    lines = source.split("\n")
    blocks: List[Dict[str, Any]] = []
    i = 0
    current_page: Optional[int] = 1

    def marker_page(line: str) -> Optional[int]:
        return extract_page(line.strip())

    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.strip()

        if not line:
            i += 1
            continue

        # A standalone page marker updates provenance state and is not content.
        page_marker = marker_page(line)
        if page_marker is not None and all(
            pattern.fullmatch(line) for pattern in PAGE_PATTERNS
            if pattern.fullmatch(line)
        ):
            current_page = page_marker
            i += 1
            continue

        # Also handle a line containing only a page marker when formatting
        # differs slightly from the strict patterns above.
        if page_marker is not None and clean_page_markers(line) == "":
            current_page = page_marker
            i += 1
            continue

        block_page = page_marker if page_marker is not None else current_page

        # Fenced code is treated as prose-like content.
        if line.startswith("```"):
            buf = [line]
            i += 1
            while i < len(lines):
                buf.append(lines[i])
                if lines[i].strip().startswith("```"):
                    i += 1
                    break
                i += 1
            blocks.append({
                "type": "text",
                "text": clean_page_markers(normalize_text("\n".join(buf))),
                "page": block_page,
            })
            continue

        # Markdown table: header + separator + one or more pipe rows.
        if (
            i + 1 < len(lines)
            and "|" in line
            and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1].strip())
        ):
            table = [line, lines[i + 1].strip()]
            i += 2
            while i < len(lines):
                nxt = lines[i].strip()
                if not nxt or "|" not in nxt:
                    break
                # If a page marker appears inside the table region, stop so it
                # can be processed as a provenance marker on the next loop.
                if extract_page(nxt) is not None and clean_page_markers(nxt) == "":
                    break
                table.append(nxt)
                i += 1
            blocks.append({
                "type": "table",
                "text": "\n".join(table),
                "page": block_page,
            })
            continue

        is_srotas_title = bool(re.match(r"^\s*(?:(?:Pranvah|Rasavah|Rasvah|Udakvah|Mootravah|Annavah|Manovah|Raktavah)\s+Srotas\b|Patients with\s+(?:Pranvah|Rasavah|Udakvah|Mootravah|Annavah|Manovah|Raktavah|Hrudrog|Prameh)\b)", line, re.I))
        if re.match(r"^\s*#{1,6}\s+", line) or is_srotas_title:
            blocks.append({
                "type": "title",
                "text": clean_page_markers(line),
                "page": block_page,
            })
            i += 1
            continue

        if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", line):
            buf = [line]
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if not nxt:
                    break
                if extract_page(nxt) is not None and clean_page_markers(nxt) == "":
                    break
                if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", nxt):
                    buf.append(nxt)
                    i += 1
                else:
                    break
            blocks.append({
                "type": "list_item",
                "text": clean_page_markers("\n".join(buf)),
                "page": block_page,
            })
            continue

        buf = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt:
                break
            if extract_page(nxt) is not None and clean_page_markers(nxt) == "":
                break
            if re.match(r"^\s*#{1,6}\s+", nxt) or re.match(r"^\s*(?:(?:Pranvah|Rasavah|Rasvah|Udakvah|Mootravah|Annavah|Manovah|Raktavah)\s+Srotas\b|Patients with\s+(?:Pranvah|Rasavah|Udakvah|Mootravah|Annavah|Manovah|Raktavah|Hrudrog|Prameh)\b)", nxt, re.I):
                break
            if (
                i + 1 < len(lines)
                and "|" in nxt
                and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1].strip())
            ):
                break
            if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", nxt):
                break
            buf.append(nxt)
            i += 1

        blocks.append({
            "type": "text",
            "text": clean_page_markers(normalize_text(" ".join(buf))),
            "page": block_page,
        })

    return [b for b in blocks if normalize_text(b.get("text", ""))]

def title_like(text: str) -> bool:
    s = normalize_text(text).lstrip("# ").strip()
    if not s:
        return False
    if re.match(r"^#{1,6}\s+", text):
        return True
    if len(s) <= 100 and s.upper() == s and re.search(r"[A-Z]", s):
        return True
    low = s.lower().rstrip(":")
    if low in HEADING_WORDS:
        return True
    if low.startswith("during sansarga"):
        return True
    if any(low.startswith(w + ":") for w in HEADING_WORDS):
        return True
    return False

def is_signature(text: str) -> bool:
    s = normalize_text(text)
    return any(p.match(s) for p in SIGNATURE_PATTERNS)

def hard_split(text: str, limit: int) -> List[str]:
    if limit <= 0:
        return [text]
    text = normalize_text(text)
    if len(text) <= limit:
        return [text]

    out: List[str] = []
    rest = text
    while len(rest) > limit:
        cut = limit
        # Prefer whitespace inside the hard limit.
        ws = rest.rfind(" ", 0, limit + 1)
        if ws >= max(40, int(limit * 0.55)):
            cut = ws
        part = rest[:cut].strip()
        if not part:
            part = rest[:limit].strip()
            cut = limit
        out.append(part)
        rest = rest[cut:].strip()
    if rest:
        out.append(rest)
    return out

def split_long_text(text: str, limit: int = TARGET_CHARS) -> List[str]:
    """
    Split prose without exceeding limit.

    Preference order:
    1. sentence-ending punctuation reasonably close to target
    2. paragraph/newline boundary
    3. semicolon
    4. whitespace
    5. hard split as final fallback

    The function never returns a piece longer than limit.
    """
    text = clean_page_markers(text)
    if len(text) <= limit:
        return [text]

    out: List[str] = []
    rest = text

    while len(rest) > limit:
        window = rest[: limit + 1]
        lower_bound = max(1, int(limit * 0.55))
        candidates: List[int] = []

        # Sentence endings.
        for m in re.finditer(r"[.!?।](?=\s|$)", window):
            pos = m.end()
            if pos >= lower_bound:
                candidates.append(pos)

        # Prefer the latest sentence boundary, but don't force a boundary
        # that would leave a clearly unfinished fragment.
        cut = max(candidates) if candidates else 0

        if not cut:
            for m in re.finditer(r"\n+", window):
                pos = m.start()
                if pos >= lower_bound:
                    cut = pos
            if not cut:
                for m in re.finditer(r";(?=\s|$)", window):
                    pos = m.end()
                    if pos >= lower_bound:
                        cut = pos

        if not cut:
            ws = rest.rfind(" ", 0, limit + 1)
            cut = ws if ws >= lower_bound else limit

        part = rest[:cut].strip()
        remainder = rest[cut:].strip()

        if not part:
            part = rest[:limit].strip()
            cut = limit
            remainder = rest[cut:].strip()

        # If the next piece begins lowercase and the current piece does not
        # end in punctuation, move the split backward to a safer punctuation
        # boundary when one exists.
        if (
            remainder
            and remainder[0].islower()
            and not re.search(r"[.!?।:]$", part)
        ):
            safer = None
            for m in re.finditer(r"[.!?।:](?=\s|$)", part):
                safer = m.end()
            if safer:
                part = rest[:safer].strip()
                remainder = rest[safer:].strip()

        # Absolute safety.
        if len(part) > limit:
            part = part[:limit].rstrip()
            remainder = rest[len(part):].strip()

        out.append(part)
        rest = remainder

    if rest:
        out.append(rest)

    return [x for x in out if x]

def parse_table_row(row: str) -> List[str]:
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [normalize_text(x) for x in s.split("|")]

def render_table_row(cells: List[str]) -> str:
    return "| " + " | ".join(cells) + " |"

def is_group_header_row(row: str) -> Tuple[bool, Optional[str]]:
    cells = [c.strip() for c in parse_table_row(row) if c.strip()]
    if not cells:
        return False, None
    first = cells[0]
    if len(cells) >= 2 and all(c.lower() == first.lower() for c in cells):
        return True, first
    if re.search(r'(?:srotas\s+vyadhi|raktavah\s+srotas|heart diseases|diabetes|renal failure|ibs|liver|psychiatric|people with|patients with)', first, re.I):
        if len(cells) == 1 or all(c.lower() == first.lower() for c in cells) or (len(cells) > 1 and not any(re.search(r'\d+-\d+-\d+', c) for c in cells)):
            return True, first
    return False, None


def get_row_severity(row: str, prev_severity: Optional[str] = None) -> Optional[str]:
    cells = parse_table_row(row)
    c0 = cells[0].lower() if cells else ""
    if "mild" in c0:
        return "mild"
    elif "moderate" in c0:
        return "moderate"
    elif "severe" in c0:
        return "severe"
    elif not c0 and prev_severity:
        return prev_severity
    return None


def split_table_block(table_text: str, target: int = TARGET_CHARS, comorbidity: Optional[str] = None) -> Tuple[List[str], Optional[str]]:
    """
    Split Markdown tables by rows, preserving severity blocks as atomic units.
    Splits at row boundaries only, never dividing an individual table row in half.
    Returns (chunks, detected_comorbidity).
    """
    lines = [x.strip() for x in table_text.splitlines() if x.strip()]
    if len(lines) < 2:
        return hard_split(normalize_text(table_text), target), comorbidity

    header_cells = parse_table_row(lines[0])
    header = render_table_row(header_cells)
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |"
    raw_rows = lines[2:]

    if not raw_rows:
        return hard_split("\n".join(lines), target), comorbidity

    detected_comorbidity = comorbidity
    data_rows = []
    for r in raw_rows:
        is_hdr, comorb = is_group_header_row(r)
        if is_hdr and not detected_comorbidity:
            detected_comorbidity = comorb
            continue
        data_rows.append(render_table_row(parse_table_row(r)))

    # Group into severity blocks
    blocks: List[Tuple[Optional[str], List[str]]] = []
    current_sev = None
    current_block_rows = []

    for r in data_rows:
        sev = get_row_severity(r, current_sev)
        if sev != current_sev and current_block_rows:
            blocks.append((current_sev, current_block_rows))
            current_block_rows = [r]
            current_sev = sev
        else:
            current_block_rows.append(r)
            if sev:
                current_sev = sev
    if current_block_rows:
        blocks.append((current_sev, current_block_rows))

    header_block = header + "\n" + separator
    header_len = len(header_block)

    chunks: List[str] = []
    curr_rows: List[str] = []
    curr_len = header_len

    def flush() -> None:
        nonlocal curr_rows, curr_len
        if curr_rows:
            content = header_block + "\n" + "\n".join(curr_rows)
            chunks.append(content)
        curr_rows = []
        curr_len = header_len

    for sev, rows in blocks:
        block_text = "\n".join(rows)
        block_len = len(block_text) + 1

        if curr_rows and (curr_len + block_len > target):
            flush()

        if header_len + block_len <= target:
            curr_rows.extend(rows)
            curr_len += block_len
        else:
            flush()
            for r in rows:
                r_len = len(r) + 1
                if curr_len + r_len > target and curr_rows:
                    flush()
                curr_rows.append(r)
                curr_len += r_len
            flush()

    flush()
    return [c for c in chunks if normalize_text(c)], detected_comorbidity


def make_chunks_from_blocks(blocks: List[Dict[str, Any]], doc_id: str = "DOC") -> List[Dict[str, Any]]:
    """
    Track full heading hierarchy, associate headings with following tables/content,
    filter disclaimer boilerplate, coalesce adjacent prose, and split tables/prose
    ensuring chunk content <= TARGET_CHARS with prepended hierarchical context.
    """
    current_section: Optional[str] = None
    current_subsection: Optional[str] = None
    current_sub_sub: Optional[str] = None
    current_page: Optional[int] = 1
    in_disclaimer_section: bool = False

    processed_items: List[Dict[str, Any]] = []

    i = 0
    while i < len(blocks):
        b = blocks[i]
        raw = b.get("text", "")
        page = b.get("page")
        if page is not None:
            current_page = page

        text = strip_placeholder_lines(raw)
        text = clean_page_markers(text)

        if not text or is_placeholder_only(raw) or is_ocr_garbage(text):
            i += 1
            continue

        first_line = text.splitlines()[0] if text else ""
        is_heading = (b.get("type") == "title") or first_line.startswith("#")

        if is_heading:
            h_clean = clean_heading(first_line)

            if "disclaimer" in h_clean.lower():
                in_disclaimer_section = True
                i += 1
                continue

            if any(p.search(h_clean) for p in IGNORE_HEADING_PATTERNS) or is_disclaimer_boilerplate(h_clean):
                i += 1
                continue

            if any(p.search(h_clean) for p in DOC_TITLE_PATTERNS):
                i += 1
                continue

            in_disclaimer_section = False

            level = len(first_line) - len(first_line.lstrip("#"))
            if level == 1:
                current_section = h_clean
                current_subsection = None
                current_sub_sub = None
            elif level == 3:
                current_sub_sub = h_clean
            elif any(p.search(h_clean) for p in MAJOR_SECTION_PATTERNS):
                current_section = h_clean
                current_subsection = None
                current_sub_sub = None
            elif any(p.search(h_clean) for p in SUB_SUBSECTION_PATTERNS):
                current_sub_sub = h_clean
            else:
                if current_section is None:
                    current_section = h_clean
                else:
                    current_subsection = h_clean
                    current_sub_sub = None

            i += 1
            continue

        if in_disclaimer_section:
            i += 1
            continue

        if is_signature(text) or is_disclaimer_boilerplate(text):
            i += 1
            continue

        ctype = b.get("type", "text")
        processed_items.append({
            "type": ctype,
            "text": text,
            "page": current_page,
            "section": current_section,
            "subsection": current_subsection,
            "sub_subsection": current_sub_sub,
        })
        i += 1

    # Coalesce adjacent compatible short prose blocks with identical section hierarchy.
    coalesced: List[Dict[str, Any]] = []
    for item in processed_items:
        if (
            coalesced
            and item["type"] in {"text", "list_item"}
            and coalesced[-1]["type"] in {"text", "list_item"}
            and coalesced[-1]["section"] == item["section"]
            and coalesced[-1]["subsection"] == item["subsection"]
            and coalesced[-1]["sub_subsection"] == item["sub_subsection"]
            and len(coalesced[-1]["text"]) < MIN_CHUNK_CHARS
            and len(coalesced[-1]["text"]) + 1 + len(item["text"]) <= TARGET_CHARS - 300
        ):
            coalesced[-1]["text"] = normalize_text(
                coalesced[-1]["text"] + "\n" + item["text"]
            )
            if coalesced[-1].get("page") is None:
                coalesced[-1]["page"] = item.get("page")
        else:
            coalesced.append(item)

    # Split tables and prose to ensure <= TARGET_CHARS with prepended hierarchical context.
    prepared_chunks: List[Dict[str, Any]] = []
    table_counter = 0

    for item in coalesced:
        sec = item["section"]
        subsec = item["subsection"]
        subsub = item["sub_subsection"]
        ctype = item["type"]
        raw_text = item["text"]
        page = item["page"]

        if ctype == "table":
            table_counter += 1
            table_id = f"{doc_id}-p{page or 1}-t{table_counter:02d}"
            # Budget accommodates table content alongside complete breadcrumb header
            pieces, detected_comorb = split_table_block(raw_text, target=TARGET_CHARS - 350, comorbidity=subsub)
            effective_comorbidity = detected_comorb or subsub
            context_header = format_section_context(sec, subsec, subsub, effective_comorbidity)

            for part_idx, piece in enumerate(pieces, start=1):
                piece = piece.strip()
                if not piece:
                    continue

                full_content = (context_header + piece).strip()
                prepared_chunks.append({
                    "type": ctype,
                    "text": full_content,
                    "page": page,
                    "section": effective_comorbidity or subsec or sec or "",
                    "section_path": [p for p in (sec, subsec, subsub, effective_comorbidity) if p],
                    "table_id": table_id,
                    "table_part": part_idx,
                    "table_total_parts": len(pieces),
                    "is_continuation": part_idx > 1,
                    "comorbidity": effective_comorbidity,
                })
        else:
            context_header = format_section_context(sec, subsec, subsub)
            header_len = len(context_header)
            available_budget = max(400, TARGET_CHARS - header_len - 2)
            pieces = split_long_text(raw_text, limit=available_budget)

            for piece in pieces:
                piece = piece.strip()
                if not piece:
                    continue

                full_content = (context_header + piece).strip()
                if len(full_content) > TARGET_CHARS:
                    sub_pieces = hard_split(full_content, TARGET_CHARS)
                else:
                    sub_pieces = [full_content]

                for sp in sub_pieces:
                    sp = sp.strip()
                    if not sp:
                        continue
                    prepared_chunks.append({
                        "type": ctype,
                        "text": sp,
                        "page": page,
                        "section": subsec or sec or "",
                        "section_path": [p for p in (sec, subsec, subsub) if p],
                    })

    return prepared_chunks


def remove_conservative_duplicates(
    chunks: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Remove exact repeated extraction artifacts conservatively.
    Never deduplicates tables.
    """
    seen: Dict[str, int] = {}
    result: List[Dict[str, Any]] = []
    removed = 0

    for c in chunks:
        ctype = c["type"]
        norm = normalized_for_dedupe(c["text"])

        if not norm:
            continue

        known_boilerplate = (
            norm in BOILERPLATE_EXACT
            or any(h in norm for h in BOILERPLATE_HINTS)
            or is_disclaimer_boilerplate(c["text"])
        )

        dedupe_candidate = (
            ctype in {"title", "text", "list_item"}
            and len(norm) <= MAX_DEDUP_CHARS
        )

        if dedupe_candidate or known_boilerplate:
            if norm in seen:
                removed += 1
                continue
            seen[norm] = len(result)

        result.append(c)

    return result, removed


def build_chunk_records(
    document_id: str,
    document_name: str,
    disease: str,
    blocks: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    prepared = make_chunks_from_blocks(blocks, doc_id=document_id)
    prepared, duplicate_count = remove_conservative_duplicates(prepared)

    records: List[Dict[str, Any]] = []

    for idx, item in enumerate(prepared, start=1):
        content = item["text"].strip()
        if not content:
            continue

        if len(content) > TARGET_CHARS:
            pieces = hard_split(content, TARGET_CHARS)
        else:
            pieces = [content]

        for piece in pieces:
            if not piece.strip():
                continue
            record_index = len(records) + 1
            rec = {
                "chunk_id": stable_id(document_id, record_index, piece),
                "document_id": document_id,
                "document_name": document_name,
                "disease": disease,
                "section": item.get("section", ""),
                "section_path": item.get("section_path", []),
                "content_type": item["type"],
                "content": piece,
                "char_count": len(piece),
                "exclude_from_embedding": is_disclaimer_boilerplate(piece),
            }

            if item.get("page") is not None:
                rec["page"] = item["page"]
            if item.get("table_id"):
                rec["table_id"] = item["table_id"]
                rec["table_part"] = item.get("table_part", 1)
                rec["table_total_parts"] = item.get("table_total_parts", 1)
                rec["is_continuation"] = item.get("is_continuation", False)
            if item.get("comorbidity"):
                rec["comorbidity"] = item["comorbidity"]

            records.append(rec)

    return records, duplicate_count

def _normalized_table_key(text: str) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"`+", "", text)
    text = re.sub(r"\s*\|\s*", "|", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_table_page_map(md_path: Path) -> List[Tuple[str, List[int]]]:
    sidecar = md_path.with_suffix(".tables.json")
    if not sidecar.exists():
        return []
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []
    found: List[Tuple[str, List[int]]] = []
    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            table_text = obj.get("markdown") or obj.get("md") or obj.get("table") or obj.get("content") or ""
            pages = obj.get("page_numbers")
            if pages is None: pages = obj.get("pages")
            if pages is None: pages = obj.get("page")
            if table_text and pages is not None:
                if isinstance(pages, int): page_list = [pages]
                elif isinstance(pages, list): page_list = [int(x) for x in pages if str(x).isdigit()]
                else: page_list = []
                if page_list: found.append((_normalized_table_key(str(table_text)), page_list))
            for value in obj.values(): walk(value)
        elif isinstance(obj, list):
            for value in obj: walk(value)
    walk(data)
    return found


def find_table_page(table_text: str, table_page_map: List[Tuple[str, List[int]]]) -> Optional[int]:
    key = _normalized_table_key(table_text)
    if not key: return None
    for sidecar_key, pages in table_page_map:
        if key == sidecar_key and pages: return pages[0]
    for sidecar_key, pages in table_page_map:
        if pages and (key in sidecar_key or sidecar_key in key): return pages[0]
    return None


def read_source(path: Path) -> List[Dict[str, Any]]:
    if path.suffix.lower() in {".md", ".markdown", ".txt"}:
        blocks = split_blocks(path.read_text(encoding="utf-8", errors="ignore"))
        table_page_map = load_table_page_map(path) if path.suffix.lower() in {".md", ".markdown"} else []
        if table_page_map:
            for block in blocks:
                if block.get("type") == "table":
                    page = find_table_page(block.get("text", ""), table_page_map)
                    if page is not None:
                        block["page"] = page
        return blocks

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in ("blocks", "elements", "content", "items"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if isinstance(data, list):
            blocks = []
            for item in data:
                if isinstance(item, str):
                    blocks.append({"type": "text", "text": item})
                elif isinstance(item, dict):
                    text = (
                        item.get("text")
                        or item.get("content")
                        or item.get("markdown")
                        or ""
                    )
                    ctype = (
                        item.get("content_type")
                        or item.get("type")
                        or "text"
                    )
                    page = item.get("page")
                    if page is None:
                        pages = item.get("pages") or item.get("page_numbers")
                        if isinstance(pages, list) and pages:
                            page = pages[0]
                        elif isinstance(pages, int):
                            page = pages

                    blocks.append({
                        "type": "table" if ctype == "table" else ctype,
                        "text": text,
                        "page": page,
                    })
            return blocks

    raise ValueError(f"Unsupported source format: {path}")

def get_disease(path: Path) -> str:
    stem = path.stem
    if stem in DISEASE_BY_DOCUMENT:
        return DISEASE_BY_DOCUMENT[stem]

    low = stem.lower()
    for key, disease in DISEASE_BY_DOCUMENT.items():
        if key.lower() == low:
            return disease

    # Conservative filename inference for future documents.
    if "respiratory" in low or "viral" in low:
        return "respiratory_viral_infection"
    if "diabet" in low or low.startswith("dm"):
        return "diabetes"

    raise ValueError(
        f"No disease mapping configured for document: '{stem}'. "
        "Add its filename stem to DISEASE_BY_DOCUMENT."
    )

def discover_documents(input_dir: Path) -> List[Path]:
    supported = {".md", ".markdown", ".txt"}
    return sorted(
        p for p in input_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in supported
        and not p.name.endswith("_chunks.json")
        and p.name not in {"chunks.json", "chunk_summary.json"}
    )

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    documents = discover_documents(input_dir)
    if not documents:
        raise SystemExit(f"No supported documents found in {input_dir}")

    all_chunks: List[Dict[str, Any]] = []
    summary_docs: List[Dict[str, Any]] = []
    total_duplicates_removed = 0

    for path in documents:
        disease = get_disease(path)
        doc_id = document_id_for(path)

        blocks = read_source(path)
        chunks, duplicates_removed = build_chunk_records(
            doc_id, path.name, disease, blocks
        )

        total_duplicates_removed += duplicates_removed
        all_chunks.extend(chunks)

        max_chars = max((c["char_count"] for c in chunks), default=0)
        short_count = sum(
            1 for c in chunks if c["char_count"] < MIN_CHUNK_CHARS
        )
        table_count = sum(
            1 for c in chunks if c["content_type"] == "table"
        )
        page_count = sum(1 for c in chunks if "page" in c)

        doc_payload = {
            "document_id": doc_id,
            "document_name": path.name,
            "disease": disease,
            "chunk_count": len(chunks),
            "max_chunk_chars": max_chars,
            "short_chunk_count": short_count,
            "table_chunk_count": table_count,
            "page_provenance_chunk_count": page_count,
            "duplicates_removed": duplicates_removed,
            "chunks": chunks,
        }

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem)
        (output_dir / f"{doc_id}_{safe_name}_chunks.json").write_text(
            json.dumps(doc_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary_docs.append({
            "document_id": doc_id,
            "document_name": path.name,
            "disease": disease,
            "chunk_count": len(chunks),
            "max_chunk_chars": max_chars,
            "short_chunk_count": short_count,
            "table_chunk_count": table_count,
            "page_provenance_chunk_count": page_count,
            "duplicates_removed": duplicates_removed,
        })

        print(
            f"[OK] {path.name}: {len(chunks)} chunks "
            f"(max={max_chars}, tables={table_count}, "
            f"pages={page_count}, duplicates_removed={duplicates_removed})"
        )

    all_chunks_path = output_dir / "chunks.json"
    all_chunks_path.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    max_all = max((c["char_count"] for c in all_chunks), default=0)
    summary = {
        "document_count": len(summary_docs),
        "total_chunks": len(all_chunks),
        "max_chunk_chars": max_all,
        "target_chars": TARGET_CHARS,
        "min_chunk_chars": MIN_CHUNK_CHARS,
        "excluded_placeholder_count": 0,
        "duplicates_removed": total_duplicates_removed,
        "page_provenance_available": any("page" in c for c in all_chunks),
        "documents": summary_docs,
    }

    (output_dir / "chunk_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(
        f"Completed: {len(summary_docs)} documents, "
        f"{len(all_chunks)} chunks."
    )
    print(f"Maximum chunk size: {max_all}")
    print(f"Duplicates removed: {total_duplicates_removed}")
    print(
        "Page provenance: "
        + ("available where source markers exist." if summary["page_provenance_available"]
           else "not available in the extracted source; extraction must emit page markers.")
    )

if __name__ == "__main__":
    main()
