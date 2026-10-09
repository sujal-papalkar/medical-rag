"""
Prescription Generation API Endpoint.

Produces strictly validated Pydantic JSON prescription responses grounded in
authoritative Ayurvedic guidelines.
"""

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.database.repositories import PatientRepository
from app.schemas.prescriptions import (
    PrescriptionGenerateRequest,
    StructuredPrescriptionResponse,
    PatientInfo,
)
from app.rag.generation import generate_structured_prescription

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])
logger = get_logger("prescriptions-api")


@router.post("/generate", response_model=StructuredPrescriptionResponse)
def generate_prescription(payload: PrescriptionGenerateRequest):
    """
    Executes grounded clinical prescription generation:
    1. Resolves patient context if patient_id is provided.
    2. Retrieves Top-K evidence chunks from ChromaDB using the 70% Semantic + 30% Lexical reranker.
    3. Prompts Gemini with 14 strict negative grounding rules.
    4. Enforces strict Pydantic JSON validation across 3 candidate answers.
    5. Returns structured physician guidance, medicine items, separated evidence citations, and limitations.
    """
    logger.info(f"Generating prescription for query='{payload.query[:60]}...', disease={payload.disease}")

    patient_info = None
    if payload.patient_id:
        p = PatientRepository.get_by_id(payload.patient_id)
        if p:
            patient_info = PatientInfo(
                patient_id=p["id"],
                name=p["name"],
                age=p["age"],
                gender=p["gender"],
                disease=p["disease"],
                presentation=p["presentation"]
            )

    try:
        response = generate_structured_prescription(
            query=payload.query,
            disease=payload.disease or (patient_info.disease if patient_info else None),
            patient_info=patient_info,
            top_k=payload.top_k,
            confirm_override=payload.confirm_override
        )
        return response
    except Exception as exc:
        logger.error(f"Prescription generation failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Prescription generation service failure: {str(exc)}"
        )
