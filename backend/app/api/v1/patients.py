"""
Patient Profiles API Endpoints.
"""

from fastapi import APIRouter, HTTPException
from app.database.repositories import PatientRepository
from app.schemas.patients import PatientProfile, PatientListResponse, TestCaseListResponse

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=PatientListResponse)
def list_patients():
    """Returns clinical patient profiles for guideline evaluation and prescription testing."""
    patients = PatientRepository.list_patients()
    return PatientListResponse(total=len(patients), patients=patients)


@router.get("/test-cases", response_model=TestCaseListResponse)
def list_test_cases():
    """Returns benchmark RAG evaluation test cases (Test Cases 1–15)."""
    test_cases = PatientRepository.list_test_cases()
    return TestCaseListResponse(total=len(test_cases), test_cases=test_cases)


@router.get("/{patient_id}", response_model=PatientProfile)
def get_patient(patient_id: str):
    """Retrieves single patient profile by ID."""
    p = PatientRepository.get_by_id(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")
    return p
