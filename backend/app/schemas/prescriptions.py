"""
Strict Pydantic Schemas for Grounded Prescription Generation.

Enforces structured validation for:
- Patient Information
- Clinical Guidance
- Medicine Items (Formulation, Dose/Matra, Frequency, Timing/Aushadh Kal, Duration, Anupana/Sahpaan)
- Evidence Sources
- Explicit Limitations / Missing Information
"""

from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.schemas.retrieval import EvidenceSource


class PatientInfo(BaseModel):
    patient_id: Optional[str] = Field(None, description="Patient ID if selected")
    name: Optional[str] = Field(None, description="Patient name")
    age: Optional[int] = Field(None, description="Patient age")
    gender: Optional[str] = Field(None, description="Patient gender")
    disease: Optional[str] = Field(None, description="Disease category")
    presentation: Optional[str] = Field(None, description="Clinical presentation")


class MedicineItem(BaseModel):
    """
    Individual medicine item strictly grounded in retrieved guideline evidence.
    Fields where evidence does not exist in context must remain None or empty.
    """
    medicine: str = Field(..., description="Ayurvedic medicine / formulation name")
    dose: Optional[str] = Field(None, description="Matra / Dose (e.g. '1-0-1', '250 mg', '2 tabs') if specified")
    dosage_form: Optional[str] = Field(None, description="Tablet, Vati, Rasayana, Kashaya, Taila, Ghrita if specified")
    route: Optional[str] = Field(None, description="Oral, Nasya, Local Application if specified")
    frequency: Optional[str] = Field(None, description="Once daily, twice daily, thrice daily if specified")
    timing: Optional[str] = Field(None, description="Aushadh Kal (Before food, After food, Empty stomach, Bedtime) if specified")
    duration: Optional[str] = Field(None, description="Treatment duration if specified")
    anupana: Optional[str] = Field(None, description="Sahpaan / Anupana / Vehicle (Warm water, Milk, Honey, etc.) if specified")
    special_instructions: Optional[str] = Field(None, description="Precautions, contraindications, or instructions if specified")
    supporting_chunk_ids: List[str] = Field(default_factory=list, description="IDs of chunks supporting this prescription")


class ClinicalGuidance(BaseModel):
    """
    Physician guidance grounded in guideline protocols.
    """
    condition: str = Field(..., description="Clinical condition / diagnosis evaluated")
    severity_or_stage: Optional[str] = Field(None, description="Severity (Mild/Moderate/Severe) or CT Score / GFR Stage")
    guidance_summary: str = Field(..., description="Concise clinical management protocol summary")
    key_recommendations: List[str] = Field(default_factory=list, description="Specific clinical guideline rules")


class ClinicalConflict(BaseModel):
    parameter: str = Field(..., description="Parameter name: age, category, disease, comorbidity, severity, etc.")
    registered_value: Any = Field(..., description="Authoritative value from verified patient record")
    query_value: Any = Field(..., description="Conflicting value specified in physician query")
    conflict_type: str = Field(..., description="Type of conflict: demographic_mismatch, comorbidity_discrepancy, disease_mismatch, severity_contradiction")
    message: str = Field(..., description="Physician-facing explanation of the clinical conflict")


class ConflictResolutionResult(BaseModel):
    has_conflict: bool = Field(False, description="True if any clinical parameter conflicts were detected")
    requires_confirmation: bool = Field(False, description="True if physician confirmation is required")
    conflicts: List[ClinicalConflict] = Field(default_factory=list, description="List of detected clinical conflicts")
    resolution_summary: Optional[str] = Field(None, description="Summary of resolution action")


class StructuredPrescriptionResponse(BaseModel):
    """
    Complete structured prescription payload returned to the frontend.
    Validated strictly with Pydantic without heuristic fallback.
    """
    patient: PatientInfo
    clinical_guidance: ClinicalGuidance
    medicines: List[MedicineItem] = Field(default_factory=list, description="Prescribed medicine items supported by evidence")
    prescription: Optional[List[MedicineItem]] = Field(None, description="Alias for medicines matching schema contract")
    evidence_sources: List[EvidenceSource] = Field(default_factory=list, description="Top-K evidence chunks used for grounding")
    evidence: Optional[List[EvidenceSource]] = Field(None, description="Alias for evidence_sources matching schema contract")
    limitations: List[str] = Field(default_factory=list, description="Explicitly missing information or guideline boundaries")
    conflicts: List[ClinicalConflict] = Field(default_factory=list, description="Clinical conflicts detected between patient record and query")
    requires_confirmation: bool = Field(False, description="True if physician confirmation is required before generation")
    status: str = Field("success", description="'success', 'partial_success', 'insufficient_context', 'conflict_detected', 'validation_error'")
    validation_status: str = Field("valid", description="'valid', 'conflict_pending_confirmation', or 'validation_fallback'")
    model: Optional[str] = Field(None, description="LLM model used for generation")
    query: str = Field(..., description="Original clinical query")
    raw_answer: Optional[str] = Field(None, description="Raw text answer for audit/inspection")

    def model_post_init(self, __context: Any) -> None:
        if self.prescription is None:
            self.prescription = self.medicines
        if self.evidence is None:
            self.evidence = self.evidence_sources


class PrescriptionGenerateRequest(BaseModel):
    patient_id: Optional[str] = Field(None, description="Selected patient ID")
    query: str = Field(..., description="Clinical query / physician request")
    disease: Optional[str] = Field(None, description="'diabetes' or 'respiratory_viral_infection'")
    top_k: int = Field(5, ge=1, le=10, description="Top-K evidence chunks to retrieve (default: 5)")
    confirm_override: bool = Field(False, description="Set to True to confirm physician override of detected clinical conflicts")
