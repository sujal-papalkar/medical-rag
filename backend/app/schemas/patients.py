"""
Pydantic Schemas for Patients.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class PatientProfile(BaseModel):
    id: str
    name: str
    age: int
    gender: str
    disease: str
    disease_label: str
    presentation: str
    clinical_query: str
    is_test: Optional[bool] = False
    test_number: Optional[int] = None
    expected_behavior: Optional[str] = None
    supporting_source_page: Optional[int] = None
    pass_status: Optional[str] = None
    failure_reason: Optional[str] = None


class PatientListResponse(BaseModel):
    total: int
    patients: List[PatientProfile]


class TestCaseListResponse(BaseModel):
    total: int
    test_cases: List[PatientProfile]

