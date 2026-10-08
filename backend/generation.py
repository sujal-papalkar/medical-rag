"""
Grounded Generation Layer for Medical RAG System.

Flow:
1. Accepts physician/clinical query (and optional disease constraint).
2. Reuses existing `retrieval_service.retrieve(query=query, disease=disease, top_k=5)`
   which fetches ChromaDB Top-20 candidates and executes the existing 70% semantic + 30% lexical reranker.
3. Formats the final Top-5 reranked chunks into an evidence context block containing:
   chunk_id, document_name, disease, section, page, content.
4. Invokes Gemini LLM with strict clinical grounding instructions to prevent hallucination.
5. Returns structured output separating answer guidance, evidence sources, and limitations.
"""

import os
import sys
import re
import time
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError, APIError

# ============================================================
# RESOLVE PATHS & ENVIRONMENT
# ============================================================

CURRENT_DIR = Path(__file__).resolve().parent
ENV_PATH = CURRENT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Ensure backend directory is in sys.path for clean imports
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Import the existing retrieval service singleton
try:
    from evaluation.retrieval_service import get_retrieval_service
except ImportError:
    # If called from root directory
    from backend.evaluation.retrieval_service import get_retrieval_service

# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_GENERATION_MODEL = os.getenv("GEMINI_GENERATION_MODEL", "gemini-2.5-flash")
FALLBACK_MODELS = ["gemini-3.5-flash","gemini-3.5-flash-lite"]
DEFAULT_TOP_K = 5
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 2


# ============================================================
# PROMPT TEMPLATE
# ============================================================

STRICT_GROUNDING_SYSTEM_PROMPT = """You are an Ayurvedic clinical guideline assistant for registered Ayurvedic physicians.

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

4. Every dose, vehicle, timing, and frequency associated with a medicine
   must be supported by the retrieved context.

5. Do NOT combine information from different medicines or different
   clinical conditions unless the guideline explicitly connects them.

6. Do NOT assume that a medicine mentioned for one severity, age group,
   symptom, comorbidity, or clinical condition applies to another.

7. If the requested information is not available in the retrieved context,
   explicitly write:
   "Not specified in the provided guideline."

8. Do NOT fill missing information using general medical knowledge.

9. Do NOT add recommendations merely because they are medically reasonable.

10. If the guideline provides multiple treatment options, report them as
    stated. Do not choose one unless the guideline explicitly specifies
    which one should be selected.

11. Preserve the clinical conditions, thresholds, severity/stage,
    age groups, and comorbidities specified in the guideline.

12. For every important treatment statement, cite the supporting source
    using:
    [Chunk ID | Document | Section | Page]

13. Limitations must only state information that is genuinely absent from
    the retrieved context. Do not invent limitations or clinical facts.

14. If the retrieved context does not contain enough evidence to answer
    the question safely, say so rather than guessing.

OUTPUT RULES:

- Answer the physician's question directly.
- Prefer a structured format/table when listing medicines and their
  Matra, Sahpaan, Aushadh Kal, or frequency.
- Structure your response using the following three distinct sections:
  ### 1. Clinical Guidance
  ### 2. Evidence from Retrieved Guidelines
  ### 3. Limitations & Missing Information
- Do not add unnecessary medical advice.
- Do not introduce information outside the retrieved guideline.
- Accuracy and grounding are more important than completeness.

FINAL SELF-CHECK BEFORE ANSWERING:

For every clinical claim, verify:
✓ Is it explicitly supported by the retrieved context?
✓ Is the medicine actually present?
✓ Is the dose actually present?
✓ Is the vehicle actually present?
✓ Is the timing/frequency actually present?
✓ Does it apply to this patient's condition/severity/age/comorbidity?

If any answer is NO, remove the claim or state:
"Not specified in the provided guideline."

RETRIEVED GUIDELINE CONTEXT:
{context}

PATIENT / USER QUERY:
{query}
"""


# ============================================================
# CONTEXT FORMATTER
# ============================================================

def format_context_block(chunks: List[Dict[str, Any]]) -> str:
    """
    Constructs a structured context block containing provenance and content
    for each retrieved chunk.
    """
    if not chunks:
        return "No clinical guideline context available."

    context_segments = []
    for index, c in enumerate(chunks, 1):
        chunk_id = c.get("chunk_id", "UNKNOWN")
        doc_name = c.get("document_name", "UNKNOWN")
        disease = c.get("disease", "N/A")
        section = c.get("section", "N/A")
        page = c.get("page", "N/A")
        content = (c.get("content") or "").strip()

        segment = (
            f"[GUIDELINE EVIDENCE CHUNK {index}]\n"
            f"- Chunk ID      : {chunk_id}\n"
            f"- Document Name : {doc_name}\n"
            f"- Disease       : {disease}\n"
            f"- Section       : {section}\n"
            f"- Page          : {page}\n"
            f"- Content:\n{content}\n"
        )
        context_segments.append(segment)

    return "\n---\n".join(context_segments)


def extract_source_metadata(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts minimal source metadata list from retrieved chunks for structured output.
    """
    sources = []
    for c in chunks:
        sources.append({
            "chunk_id": c.get("chunk_id"),
            "document_name": c.get("document_name"),
            "disease": c.get("disease"),
            "section": c.get("section"),
            "page": c.get("page"),
            "rank": c.get("rank"),
            "distance": c.get("distance")
        })
    return sources


# ============================================================
# LLM GENERATION WITH RETRY & FALLBACK
# ============================================================

def call_gemini_with_fallback(
    client: genai.Client,
    prompt: str,
    primary_model: str = DEFAULT_GENERATION_MODEL
) -> Dict[str, Any]:
    """
    Invokes Gemini with exponential backoff for transient 503/429 errors,
    and automatic fallback to secondary models if primary model is unavailable.
    """
    models_to_attempt = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]
    last_error: Optional[Exception] = None

    for model_name in models_to_attempt:
        backoff = INITIAL_BACKOFF_SECONDS
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    return {
                        "text": response.text.strip(),
                        "model": model_name,
                        "attempts": attempt
                    }
            except (ServerError, APIError) as exc:
                last_error = exc
                code = getattr(exc, "code", None)
                err_msg = str(exc)
                # If daily quota is exhausted for this model (takes 24h to reset), immediately move to fallback model
                if "PerDay" in err_msg:
                    break
                # Retry on 503 (high demand) or 429 (transient per-minute rate limit)
                if code in (503, 429) and attempt < MAX_RETRIES:
                    delay = backoff
                    delay_match = re.search(r"retryDelay': '(\d+)s'", err_msg)
                    if delay_match:
                        delay = max(backoff, int(delay_match.group(1)) + 2)
                    time.sleep(delay)
                    backoff *= 2
                    continue
                break
            except Exception as exc:
                last_error = exc
                break

    raise RuntimeError(f"All Gemini generation attempts failed. Last error: {last_error}")


# ============================================================
# MAIN GENERATION PIPELINE
# ============================================================

def generate_response(
    query: str,
    disease: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
    num_candidates: int = 3
) -> Dict[str, Any]:
    """
    Executes grounded RAG generation for a clinical query, generating 3 independent candidate answers.

    Flow:
    1. Validates inputs & API key.
    2. Reuses existing `retrieval_service.retrieve()` to get Top-20 ChromaDB
       candidates and apply the existing 70% semantic + 30% lexical reranker.
       Retrieval and reranking occur exactly ONCE.
    3. Takes Top-5 reranked chunks.
    4. Builds single grounded context block.
    5. Calls Gemini LLM to independently generate Candidate 1, Candidate 2, and Candidate 3
       using the SAME query and SAME Top-5 evidence context.
    6. Returns structured response with all 3 candidates and source provenance.
    """
    # 1. Input validation
    if not query or not query.strip():
        return {
            "query": query,
            "disease": disease,
            "candidates": [],
            "answer": "Error: Clinical query cannot be empty.",
            "sources": [],
            "status": "invalid_query"
        }

    # 2. Check API key
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "query": query,
            "disease": disease,
            "candidates": [],
            "answer": "Error: GEMINI_API_KEY is not configured in .env or environment.",
            "sources": [],
            "status": "missing_api_key"
        }

    # 3. Retrieve Top-K chunks using existing retrieval service (ONCE)
    try:
        retrieval_service = get_retrieval_service()
        retrieved_chunks = retrieval_service.retrieve(
            query=query.strip(),
            disease=disease.strip() if disease and disease.strip() else None,
            top_k=top_k
        )
    except Exception as exc:
        return {
            "query": query,
            "disease": disease,
            "candidates": [],
            "answer": f"Error during guideline retrieval: {str(exc)}",
            "sources": [],
            "status": "retrieval_error"
        }

    # 4. Handle no retrieved chunks
    if not retrieved_chunks:
        return {
            "query": query,
            "disease": disease,
            "candidates": [],
            "answer": "The available guideline context is insufficient to provide an answer. No matching guideline evidence was retrieved for the query.",
            "sources": [],
            "status": "insufficient_context"
        }

    # 5. Extract sources for response payload (single set of sources)
    sources = extract_source_metadata(retrieved_chunks)

    # 6. Format context block for the prompt (single Top-5 context block)
    context_block = format_context_block(retrieved_chunks)

    # 7. Construct grounded prompt (same strict grounding prompt)
    prompt = STRICT_GROUNDING_SYSTEM_PROMPT.format(
        context=context_block,
        context_block=context_block,
        query=query.strip()
    )

    # 8. Generate exactly num_candidates independent answers
    genai_client = genai.Client(api_key=api_key)
    candidates = []

    for candidate_id in range(1, num_candidates + 1):
        if candidate_id > 1:
            time.sleep(1.2)
        try:
            gen_result = call_gemini_with_fallback(
                client=genai_client,
                prompt=prompt,
                primary_model=DEFAULT_GENERATION_MODEL
            )
            cand_text = gen_result["text"]
            cand_model = gen_result["model"]
            candidates.append({
                "candidate_id": candidate_id,
                "answer": cand_text,
                "model": cand_model,
                "status": "success"
            })
            print(f"Candidate {candidate_id} generated", flush=True)
        except Exception as exc:
            print(f"Candidate {candidate_id} generation failed: {str(exc)}", flush=True)
            candidates.append({
                "candidate_id": candidate_id,
                "answer": "",
                "model": None,
                "status": "failed",
                "error": str(exc)
            })

    # 9. Determine overall status and backward compatibility fields
    successful_candidates = [c for c in candidates if c.get("status") == "success" and c.get("answer")]
    if len(successful_candidates) == num_candidates:
        status = "success"
    elif len(successful_candidates) > 0:
        status = "partial_success"
    else:
        status = "generation_api_error"

    primary_answer = successful_candidates[0]["answer"] if successful_candidates else ""
    primary_model = successful_candidates[0]["model"] if successful_candidates else "unknown"

    # 10. Return structured output with all candidates
    return {
        "query": query,
        "disease": disease,
        "candidates": candidates,
        "sources": sources,
        "status": status,
        "answer": primary_answer,
        "model": primary_model,
        "context_block": context_block
    }


# Convenience alias matching naming conventions
generate_clinical_response = generate_response


# ============================================================
# CLI ENTRYPOINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Grounded Medical RAG Generation Layer"
    )
    parser.add_argument(
        "query",
        type=str,
        nargs="?",
        default="A patient with diabetes mellitus has Trushna (polydipsia). Retrieve the treatment information including medicine, Matra, and Sahpaan.",
        help="Physician clinical query"
    )
    parser.add_argument(
        "--disease",
        type=str,
        default=None,
        help="Optional disease filter ('diabetes' or 'respiratory_viral_infection')"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Number of reranked evidence chunks to use (default: 5)"
    )
    parser.add_argument(
        "--num-candidates",
        type=int,
        default=3,
        help="Number of candidate answers to generate (default: 3)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response"
    )

    args = parser.parse_args()

    print("=" * 80)
    print("AYURVEDIC MEDICAL RAG: GROUNDED GENERATION (3 CANDIDATES)")
    print("=" * 80)
    print(f"Query      : {args.query}")
    print(f"Disease    : {args.disease or 'Unfiltered'}")
    print(f"Top-K      : {args.top_k}")
    print(f"Candidates : {args.num_candidates}")
    print("-" * 80)

    result = generate_response(
        query=args.query,
        disease=args.disease,
        top_k=args.top_k,
        num_candidates=args.num_candidates
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(f"Status  : {result.get('status')} (Primary Model: {result.get('model', 'N/A')})")
    print(f"Total Candidates: {len(result.get('candidates', []))}")
    for cand in result.get("candidates", []):
        cid = cand.get("candidate_id")
        c_status = cand.get("status", "unknown")
        c_model = cand.get("model", "N/A")
        print(f"\n==================== CANDIDATE {cid} (Model: {c_model} | Status: {c_status}) ====================")
        print(cand.get("answer") or cand.get("error", "No output"))
    print("\n--- SOURCES USED ---")
    for s in result.get("sources", []):
        print(f"  [Rank #{s.get('rank')}] Chunk ID: {s.get('chunk_id')} | Page: {s.get('page')} | Doc: {s.get('document_name')} | Sec: {str(s.get('section'))[:50]}")
    print("=" * 80)


if __name__ == "__main__":
    main()
