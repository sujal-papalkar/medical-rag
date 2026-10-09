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


class PatientListResponse(BaseModel):
    total: int
    patients: List[PatientProfile]
