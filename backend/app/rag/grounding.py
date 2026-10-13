"""
Grounding Prompts and Clinical Rules for Strict Ayurvedic RAG Generation.

Enforces:
1. 14 negative grounding constraints preventing clinical hallucination.
2. Strict Pydantic JSON structure for physician guidance, medicine items, citations, and limitations.
"""

from typing import List, Dict, Any

STRICT_GROUNDING_SYSTEM_RULES = """You are an Ayurvedic clinical guideline assistant for registered Ayurvedic physicians.

IMPORTANT:
Your answer must be based ONLY on the retrieved guideline context provided below.
Do NOT use external medical knowledge, assumptions, memory, or inference.

STRICT GROUNDING RULES:

1. Use ONLY information explicitly supported by the retrieved context.
2. Do NOT invent or infer:
   - medicines/formulations
   - dosage/Matra
   - vehicle/Sahpaan
   - timing/Aushadh Kal
   - frequency
   - duration of treatment
   - contraindications
   - drug interactions
   - precautions
   - clinical recommendations
   - diagnostic criteria
   - investigations
3. Every medicine mentioned must appear in the retrieved context.
4. Every dose, vehicle, timing, and frequency associated with a medicine must be supported by the retrieved context.
5. Do NOT combine information from different medicines or different clinical conditions unless the guideline explicitly connects them.
7. CLINICAL TABLE MATCHING:
   - Identify patient vitals, biomarkers, clinical test scores, age, and explicit comorbidities from the patient context.
   - Match these values against the corresponding criteria, thresholds, or rows in the retrieved guideline tables (e.g. matching SpO2, HRCT score, or age to the row specifying that range).
   - Prescribe strictly and exclusively from the table row matching the patient's verified stage or condition.
   - Do NOT combine formulations across different severity rows, different age brackets, or unrelated comorbidity tables.
9. Do NOT fill missing information using general medical knowledge.
10. Do NOT add recommendations merely because they are medically reasonable.
11. If the guideline provides multiple treatment options, report them as stated. Do not choose one unless the guideline explicitly specifies which one should be selected.
12. Preserve the clinical conditions, thresholds, severity/stage, age groups, and comorbidities specified in the guideline.
13. EXACT CITATIONS: Attach each medicine to its EXACT supporting chunk ID and verified page number from the table where it appears.
    - Do NOT attach multiple unrelated retrieved chunk IDs to every medicine.
    - Each medicine must have ONLY the chunk ID(s) of the specific guideline table/row that prescribes it.
14. Limitations must only state information that is genuinely absent from the retrieved context. Do not invent limitations or clinical facts.
15. If clinical context or supporting evidence is insufficient (e.g. unspecified duration, dosage form, or missing clinical parameters), state the exact limitation instead of guessing.
"""

STRUCTURED_JSON_INSTRUCTIONS = """
OUTPUT FORMAT REQUIREMENT:
You MUST respond with a valid, parseable JSON object adhering strictly to the following JSON schema:

{
  "clinical_guidance": {
    "condition": "Specific condition or presentation diagnosed from query",
    "severity_or_stage": "Stage, severity, or CT score threshold from context if mentioned, otherwise null",
    "guidance_summary": "Direct clinical guideline summary based only on context",
    "key_recommendations": [
      "Explicit guideline rule 1 supported by context",
      "Explicit guideline rule 2 supported by context"
    ]
  },
  "medicines": [
    {
      "medicine": "Exact Ayurvedic medicine/formulation name appearing in context",
      "dose": "Matra / dose (e.g. '1-0-0', '2-2-2', or '1-0-1') if specified in context, else null",
      "dosage_form": "Tablet, Vati, Rasayana, Kashaya, etc. if specified in context, else null",
      "route": "Oral, Nasya, Local if specified in context, else null",
      "frequency": "Once daily, twice daily, three times a day, etc. if specified in context, else null",
      "timing": "Aushadh Kal (Rasayan kal, Nisha kal, after food, etc.) if specified, else null",
      "duration": "Duration of course if specified, else null",
      "anupana": "Sahpaan / vehicle (with honey/ warm water, warm water, etc.) if specified, else null",
      "special_instructions": "Special precautions or instructions if specified, else null",
      "supporting_chunk_ids": ["EXACT_CHUNK_ID_FROM_WHICH_THIS_MEDICINE_WAS_EXTRACTED"]
    }
  ],
  "limitations": [
    "Information genuinely missing or not specified in the retrieved guidelines (e.g. duration not specified)"
  ]
}

DO NOT include any Markdown code fence outside the JSON (e.g. no ```json). Just the raw JSON object.
Do NOT invent fields or add medicines not present in the evidence.
"""


def format_context_block(chunks: List[Dict[str, Any]]) -> str:
    """Formats retrieved evidence chunks into an authoritative context block."""
    if not chunks:
        return "No clinical guideline context available."

    segments = []
    for idx, c in enumerate(chunks, 1):
        cid = c.get("chunk_id", "UNKNOWN")
        doc = c.get("document_name", "UNKNOWN")
        dis = c.get("disease", "N/A")
        sec = c.get("section", "N/A")
        page = c.get("page", "N/A")
        content = (c.get("content") or "").strip()

        segment = (
            f"[GUIDELINE EVIDENCE CHUNK {idx}]\n"
            f"- Chunk ID      : {cid}\n"
            f"- Document Name : {doc}\n"
            f"- Disease       : {dis}\n"
            f"- Section       : {sec}\n"
            f"- Page          : {page}\n"
            f"- Content:\n{content}\n"
        )
        segments.append(segment)

    return "\n---\n".join(segments)


def build_generation_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    profile: Any = None
) -> str:
    """Builds the complete grounded generation prompt for Gemini with clinical directives."""
    context_block = format_context_block(chunks)

    clinical_directive = ""
    if profile:
        matched_tbl = getattr(profile, "matched_table_name", None)
        matched_pg = getattr(profile, "matched_page", None)
        is_adult = getattr(profile, "is_adult", None)
        age = getattr(profile, "age", None)
        sev = getattr(profile, "severity", None)
        comorb = getattr(profile, "comorbidities", [])

        directive_lines = ["[CLINICAL PROFILE & TABLE RESOLUTION]"]
        if age is not None:
            directive_lines.append(f"- Patient Age: {age} years ({'Adult (>=15)' if is_adult else 'Pediatric (<15)'})")
        elif is_adult is not None:
            directive_lines.append(f"- Patient Category: {'Adult (>=15 years)' if is_adult else 'Pediatric (<15 years)'}")

        if sev:
            directive_lines.append(f"- Severity / Stage: {sev.upper()}")

        if comorb:
            directive_lines.append(f"- Documented Comorbidities: {', '.join(comorb)}")
        else:
            directive_lines.append("- Comorbidities: None / Uncomplicated")

        if matched_tbl:
            directive_lines.append(f"- Matched Guideline Table: {matched_tbl} (Page {matched_pg})")
            directive_lines.append(
                "- INSTRUCTION: Prescribe strictly and exclusively from this matched guideline table. "
                "Do NOT mix formulations from comorbidity tables (diabetes, cardiac, renal, psychiatric, gastrointestinal) "
                "or pediatric tables unless explicitly documented in the patient profile."
            )

        clinical_directive = "\n".join(directive_lines) + "\n\n"

    prompt = (
        f"{STRICT_GROUNDING_SYSTEM_RULES}\n\n"
        f"{clinical_directive}"
        f"RETRIEVED GUIDELINE CONTEXT:\n{context_block}\n\n"
        f"PATIENT / CLINICAL QUERY:\n{query}\n\n"
        f"{STRUCTURED_JSON_INSTRUCTIONS}"
    )
    return prompt
