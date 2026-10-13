"""
Strict Pydantic-Validated Prescription Generation Layer.

Workflow:
1. Reuses existing 70% Semantic + 30% Lexical retrieval service to fetch Top-K evidence chunks ONCE.
2. Builds grounded prompt with 14 strict clinical rules and JSON schema instructions.
3. Queries Gemini (primary model with automatic fallbacks and exponential backoff).
4. Generates 3 independent candidate responses.
5. Strictly parses and validates the output using Pydantic schemas (MedicineItem, ClinicalGuidance, StructuredPrescriptionResponse).
6. Handles validation failures safely without heuristic guessing or fabricating values.
7. Returns complete validated structured response with separated evidence sources and limitations.
"""

import os
import re
import json
import time
from typing import Dict, Any, List, Optional
from google import genai
from google.genai.errors import ServerError, APIError
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.prescriptions import (
    StructuredPrescriptionResponse,
    MedicineItem,
    ClinicalGuidance,
    PatientInfo,
)
from app.schemas.retrieval import EvidenceSource
from app.rag.retrieval import get_retrieval_service
from app.rag.grounding import build_generation_prompt, format_context_block
from app.rag.conflict_resolver import resolve_clinical_context
from app.rag.clinical_matcher import (
    extract_clinical_profile,
    prioritize_and_isolate_chunks,
    sanitize_prescribed_medicines,
)

logger = get_logger("prescription-generator")


def clean_json_text(text: str) -> str:
    """Strips markdown code fences and extraneous leading/trailing whitespace."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def call_gemini_with_fallback(
    client: genai.Client,
    prompt: str,
    primary_model: str = settings.GEMINI_GENERATION_MODEL
) -> Dict[str, Any]:
    """
    Invokes Gemini with exponential backoff for transient 503/429 errors,
    and fallback to secondary models if primary model is unavailable.
    """
    models_to_attempt = [primary_model] + [m for m in settings.FALLBACK_MODELS if m != primary_model]
    last_error: Optional[Exception] = None

    for model_name in models_to_attempt:
        backoff = settings.INITIAL_BACKOFF_SECONDS
        for attempt in range(1, settings.MAX_GENERATION_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={"temperature": 0.0, "top_p": 1.0, "seed": 42}
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
                if "PerDay" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                    logger.warning(f"Model {model_name} quota exhausted: {err_msg[:120]}. Falling back to next model.")
                    break
                if code in (503, 429) and attempt < settings.MAX_GENERATION_RETRIES:
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


def generate_structured_prescription(
    query: str,
    disease: Optional[str] = None,
    patient_info: Optional[PatientInfo] = None,
    patient: Optional[PatientInfo] = None,
    top_k: int = settings.DEFAULT_TOP_K,
    num_candidates: int = settings.NUM_GENERATION_CANDIDATES,
    confirm_override: bool = False
) -> StructuredPrescriptionResponse:
    """
    Executes grounded prescription generation with strict Pydantic validation:
    1. Validates query and executes universal clinical conflict detection.
    2. If conflicts are detected and unconfirmed, halts generation and requires confirmation.
    3. If resolved or confirmed, retrieves guideline evidence strictly matching clinical context.
    4. Builds grounded prompt and invokes LLM for candidate answers.
    5. Validates candidates against Pydantic models.
    6. Returns StructuredPrescriptionResponse with separated citations and conflict audit.
    """
    patient_obj = patient_info or patient or PatientInfo(disease=disease)

    # 1. Validate query
    if not query or not query.strip():
        return StructuredPrescriptionResponse(
            patient=patient_obj,
            clinical_guidance=ClinicalGuidance(
                condition="Unspecified Query",
                guidance_summary="Clinical query cannot be empty."
            ),
            status="invalid_query",
            validation_status="valid",
            query=query,
            limitations=["Empty query submitted."]
        )

    # 2. Universal Clinical Conflict Resolution
    conflict_res, profile = resolve_clinical_context(
        query=query,
        patient_info=patient_obj,
        disease=disease,
        confirm_override=confirm_override
    )

    # 3. Halt if confirmation required
    if conflict_res.requires_confirmation:
        logger.warning(
            f"Prescription generation blocked for patient {patient_obj.patient_id or 'unknown'}: "
            f"{len(conflict_res.conflicts)} clinical conflict(s) detected. Awaiting physician confirmation."
        )
        return StructuredPrescriptionResponse(
            patient=patient_obj,
            clinical_guidance=ClinicalGuidance(
                condition=patient_obj.presentation or "Clinical Conflict Detected",
                severity_or_stage=profile.severity,
                guidance_summary=(
                    f"Prescription generation blocked: {len(conflict_res.conflicts)} clinical parameter conflict(s) "
                    f"detected between authoritative patient profile and physician query. "
                    f"Physician confirmation required to proceed."
                ),
                key_recommendations=[c.message for c in conflict_res.conflicts]
            ),
            medicines=[],
            evidence_sources=[],
            limitations=[
                f"Conflict in {c.parameter}: Registered='{c.registered_value}' vs Query='{c.query_value}'. Physician confirmation required."
                for c in conflict_res.conflicts
            ],
            conflicts=conflict_res.conflicts,
            requires_confirmation=True,
            status="conflict_detected",
            validation_status="conflict_pending_confirmation",
            query=query,
            raw_answer=conflict_res.resolution_summary
        )

    # 4. Check API key
    if not settings.GEMINI_API_KEY:
        return StructuredPrescriptionResponse(
            patient=patient_obj,
            clinical_guidance=ClinicalGuidance(
                condition="Configuration Error",
                guidance_summary="GEMINI_API_KEY is not configured in environment or .env."
            ),
            conflicts=conflict_res.conflicts,
            requires_confirmation=False,
            status="missing_api_key",
            validation_status="valid",
            query=query,
            limitations=["Server API key missing."]
        )

    # 5. Retrieve Top-K evidence chunks ONCE
    try:
        retrieval_service = get_retrieval_service()
        effective_disease = profile.disease if profile.disease in ["diabetes", "respiratory_viral_infection"] else (disease.strip() if disease and disease.strip() else None)
        retrieved_chunks = retrieval_service.retrieve(
            query=query.strip(),
            disease=effective_disease,
            top_k=top_k
        )
    except Exception as exc:
        logger.error(f"Retrieval error: {exc}")
        return StructuredPrescriptionResponse(
            patient=patient_obj,
            clinical_guidance=ClinicalGuidance(
                condition="Retrieval Failure",
                guidance_summary=f"Error during guideline evidence retrieval: {str(exc)}"
            ),
            conflicts=conflict_res.conflicts,
            requires_confirmation=False,
            status="retrieval_error",
            validation_status="valid",
            query=query,
            limitations=["Database retrieval failed."]
        )

    # 6. Handle insufficient context
    if not retrieved_chunks:
        return StructuredPrescriptionResponse(
            patient=patient_obj,
            clinical_guidance=ClinicalGuidance(
                condition=patient_obj.presentation or "Clinical Inquiry",
                guidance_summary="The available guideline context is insufficient to provide an answer. No matching guideline evidence was retrieved."
            ),
            conflicts=conflict_res.conflicts,
            requires_confirmation=False,
            status="insufficient_context",
            validation_status="valid",
            query=query,
            limitations=["No relevant guideline chunks retrieved from the knowledge base."]
        )

    # 6. Prioritize and isolate chunks strictly matching clinical table
    isolated_chunks = prioritize_and_isolate_chunks(retrieved_chunks, profile)

    # 7. Extract structured evidence sources
    evidence_sources = [
        EvidenceSource(
            chunk_id=c.get("chunk_id", ""),
            document_name=c.get("document_name", ""),
            disease=c.get("disease"),
            section=c.get("section"),
            page=c.get("page"),
            rank=c.get("rank"),
            distance=c.get("distance"),
            content=c.get("content")
        )
        for c in isolated_chunks
    ]

    # 8. Build grounded prompt with clinical table directive
    prompt = build_generation_prompt(query.strip(), isolated_chunks, profile=profile)
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # 9. Generate candidates & strictly validate with Pydantic
    parsed_candidates: List[Dict[str, Any]] = []
    raw_answers: List[str] = []
    selected_model: Optional[str] = None

    for candidate_idx in range(1, num_candidates + 1):
        if candidate_idx > 1:
            time.sleep(1.0)
        try:
            gen_res = call_gemini_with_fallback(client=client, prompt=prompt)
            raw_text = gen_res["text"]
            selected_model = gen_res["model"]
            raw_answers.append(raw_text)

            json_text = clean_json_text(raw_text)
            data = json.loads(json_text)

            # Strict Pydantic parsing
            guidance_data = data.get("clinical_guidance", {})
            clinical_guidance = ClinicalGuidance(
                condition=guidance_data.get("condition", patient_obj.presentation or "Clinical Guideline Evaluation"),
                severity_or_stage=guidance_data.get("severity_or_stage", profile.severity),
                guidance_summary=guidance_data.get("guidance_summary", ""),
                key_recommendations=guidance_data.get("key_recommendations", [])
            )

            raw_meds = []
            for m in data.get("medicines", []):
                med_item = MedicineItem(
                    medicine=m.get("medicine", ""),
                    dose=m.get("dose"),
                    dosage_form=m.get("dosage_form"),
                    route=m.get("route"),
                    frequency=m.get("frequency"),
                    timing=m.get("timing"),
                    duration=m.get("duration"),
                    anupana=m.get("anupana"),
                    special_instructions=m.get("special_instructions"),
                    supporting_chunk_ids=m.get("supporting_chunk_ids", [])
                )
                raw_meds.append(med_item)

            # Sanitize medicines strictly against matched table and verified page
            sanitized_medicines = sanitize_prescribed_medicines(raw_meds, profile, isolated_chunks)

            limitations = data.get("limitations", [])
            if not isinstance(limitations, list):
                limitations = [str(limitations)]

            # Check and state limitations when details are missing in guidelines
            if profile.disease == "respiratory_viral_infection" and profile.severity == "mild":
                duration_lim = "Exact treatment duration and dosage form are not specified in the guideline for these rasayana formulations; physician clinical monitoring is recommended."
                if not any("duration" in str(lim).lower() for lim in limitations):
                    limitations.append(duration_lim)

            if profile.age is None and profile.is_adult is None:
                age_lim = "Patient age is not specified; guideline formulations vary strictly between pediatric (<15 years) and adult (>=15 years) protocols."
                if not any("age" in str(lim).lower() for lim in limitations):
                    limitations.append(age_lim)

            parsed_candidates.append({
                "clinical_guidance": clinical_guidance,
                "medicines": sanitized_medicines,
                "limitations": limitations,
                "raw": raw_text,
                "candidate_idx": candidate_idx
            })

        except (json.JSONDecodeError, ValidationError) as parse_err:
            logger.warning(f"Candidate {candidate_idx} failed strict JSON/Pydantic validation: {parse_err}")
            continue
        except Exception as exc:
            logger.error(f"Candidate {candidate_idx} generation error: {exc}")
            continue

    # 10. Selection of best valid candidate
    if parsed_candidates:
        # Choose candidate with the most complete validated medicine items and guidance, with deterministic tie-breaking
        best = max(
            parsed_candidates,
            key=lambda c: (len(c["medicines"]), len(c["clinical_guidance"].key_recommendations), -c.get("candidate_idx", 0))
        )

        all_limitations = list(best["limitations"])
        if conflict_res.conflicts:
            override_audit = f"Physician clinical override confirmed: {conflict_res.resolution_summary}"
            if override_audit not in all_limitations:
                all_limitations.insert(0, override_audit)

        return StructuredPrescriptionResponse(
            patient=patient_obj,
            clinical_guidance=best["clinical_guidance"],
            medicines=best["medicines"],
            evidence_sources=evidence_sources,
            limitations=all_limitations,
            conflicts=conflict_res.conflicts,
            requires_confirmation=False,
            status="success",
            validation_status="valid",
            model=selected_model,
            query=query,
            raw_answer=best["raw"]
        )

    # 9. Fallback if no candidate strictly conformed to JSON schema
    logger.error("All candidate answers failed strict Pydantic JSON validation. Returning controlled fallback.")
    fallback_guidance = ClinicalGuidance(
        condition=patient_obj.presentation or "Grounded Guideline Query",
        guidance_summary="Guideline evidence was retrieved, but the model output did not satisfy strict Pydantic JSON schema constraints. Raw response is available for review."
    )

    all_limitations = ["Strict schema validation could not parse structured medicine items. No medicines were fabricated."]
    if conflict_res.conflicts:
        all_limitations.insert(0, f"Physician clinical override confirmed: {conflict_res.resolution_summary}")

    return StructuredPrescriptionResponse(
        patient=patient_obj,
        clinical_guidance=fallback_guidance,
        medicines=[],
        evidence_sources=evidence_sources,
        limitations=all_limitations,
        conflicts=conflict_res.conflicts,
        requires_confirmation=False,
        status="partial_success",
        validation_status="validation_fallback",
        model=selected_model,
        query=query,
        raw_answer=raw_answers[0] if raw_answers else None
    )


def generate_candidate_dict_response(
    query: str,
    disease: Optional[str] = None,
    top_k: int = 5,
    num_candidates: int = 3
) -> Dict[str, Any]:
    """
    Candidate dictionary response generator specifically supporting GenerationEvaluator.
    Generates num_candidates independent answers and returns raw candidate texts,
    sources, and context text.
    """
    if not query or not query.strip():
        return {
            "query": query,
            "disease": disease,
            "candidates": [],
            "sources": [],
            "status": "invalid_query",
            "answer": "",
            "model": None,
            "context_block": "",
            "context_text": ""
        }

    if not settings.GEMINI_API_KEY:
        return {
            "query": query,
            "disease": disease,
            "candidates": [],
            "sources": [],
            "status": "missing_api_key",
            "answer": "",
            "model": None,
            "context_block": "",
            "context_text": ""
        }

    try:
        retrieval_service = get_retrieval_service()
        retrieved_chunks = retrieval_service.retrieve(
            query=query.strip(),
            disease=disease.strip() if disease and disease.strip() else None,
            top_k=top_k
        )
    except Exception as exc:
        logger.error(f"Retrieval error: {exc}")
        return {
            "query": query,
            "disease": disease,
            "candidates": [],
            "sources": [],
            "status": "retrieval_error",
            "answer": "",
            "model": None,
            "context_block": "",
            "context_text": ""
        }

    if not retrieved_chunks:
        return {
            "query": query,
            "disease": disease,
            "candidates": [],
            "sources": [],
            "status": "insufficient_context",
            "answer": "",
            "model": None,
            "context_block": "",
            "context_text": ""
        }

    profile = extract_clinical_profile(query=query, disease=disease)
    isolated_chunks = prioritize_and_isolate_chunks(retrieved_chunks, profile)

    sources = [
        {
            "chunk_id": c.get("chunk_id"),
            "document_name": c.get("document_name"),
            "disease": c.get("disease"),
            "section": c.get("section"),
            "page": c.get("page"),
            "rank": c.get("rank"),
            "distance": c.get("distance"),
            "content": c.get("content")
        }
        for c in isolated_chunks
    ]

    context_block = format_context_block(isolated_chunks)
    prompt = build_generation_prompt(query.strip(), isolated_chunks, profile=profile)
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    candidates = []
    for candidate_id in range(1, num_candidates + 1):
        if candidate_id > 1:
            time.sleep(1.0)
        try:
            gen_res = call_gemini_with_fallback(client=client, prompt=prompt)
            candidates.append({
                "candidate_id": candidate_id,
                "answer": gen_res["text"],
                "model": gen_res["model"],
                "status": "success"
            })
        except Exception as exc:
            logger.error(f"Candidate {candidate_id} failed: {exc}")
            candidates.append({
                "candidate_id": candidate_id,
                "answer": "",
                "model": None,
                "status": "failed",
                "error": str(exc)
            })

    successful_cands = [c for c in candidates if c.get("status") == "success" and c.get("answer")]
    if len(successful_cands) == num_candidates:
        status = "success"
    elif len(successful_cands) > 0:
        status = "partial_success"
    else:
        status = "generation_api_error"

    primary_answer = successful_cands[0]["answer"] if successful_cands else ""
    primary_model = successful_cands[0]["model"] if successful_cands else None

    return {
        "query": query,
        "disease": disease,
        "candidates": candidates,
        "sources": sources,
        "status": status,
        "answer": primary_answer,
        "model": primary_model,
        "context_block": context_block,
        "context_text": context_block
    }


def generate_response(
    query: str,
    disease: Optional[str] = None,
    top_k: int = 5,
    num_candidates: int = 3,
    patient: Optional[PatientInfo] = None,
    as_dict: Optional[bool] = None,
) -> Any:
    """
    Unified generation entrypoint.
    If called with as_dict=True or without patient (e.g. from evaluators),
    returns candidate dictionary format.
    Otherwise returns StructuredPrescriptionResponse.
    """
    if as_dict is True or (patient is None and as_dict is not False):
        return generate_candidate_dict_response(
            query=query,
            disease=disease,
            top_k=top_k,
            num_candidates=num_candidates
        )
    return generate_structured_prescription(
        query=query,
        patient=patient,
        disease=disease,
        top_k=top_k,
        num_candidates=num_candidates
    )


generate_clinical_response = generate_response
