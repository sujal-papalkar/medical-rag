"""
Unit tests for Strict Pydantic Prescription Schemas & Generation Logic.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.prescriptions import (
    MedicineItem,
    ClinicalGuidance,
    PatientInfo,
    StructuredPrescriptionResponse
)
from app.schemas.retrieval import EvidenceSource
from app.rag.generation import clean_json_text


class TestGenerationSchemas(unittest.TestCase):

    def test_clean_json_text(self):
        fenced = "```json\n{\"clinical_guidance\": {\"condition\": \"Diabetes\"}}\n```"
        cleaned = clean_json_text(fenced)
        self.assertTrue(cleaned.startswith("{"))
        self.assertTrue(cleaned.endswith("}"))

    def test_medicine_item_missing_fields_stay_none(self):
        item = MedicineItem(medicine="Zincare", dose="1-0-1")
        self.assertEqual(item.medicine, "Zincare")
        self.assertEqual(item.dose, "1-0-1")
        self.assertIsNone(item.timing)
        self.assertIsNone(item.anupana)
        self.assertIsNone(item.special_instructions)

    def test_structured_prescription_response_validation(self):
        resp = StructuredPrescriptionResponse(
            patient=PatientInfo(patient_id="PAT-DM-001", name="Rajesh"),
            clinical_guidance=ClinicalGuidance(
                condition="Type 2 Diabetes",
                guidance_summary="Follow dietary and Rasayana protocol.",
                key_recommendations=["Control blood sugar", "Take Zincare with warm water"]
            ),
            medicines=[
                MedicineItem(medicine="Zincare", dose="1-0-1", anupana="Warm water")
            ],
            evidence_sources=[
                EvidenceSource(chunk_id="DOC-123", document_name="DM RR.md", page=5)
            ],
            limitations=["Long term duration not specified in guideline."],
            status="success",
            query="Diabetes treatment"
        )
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.validation_status, "valid")
        self.assertEqual(len(resp.medicines), 1)
        self.assertEqual(resp.medicines[0].medicine, "Zincare")


if __name__ == "__main__":
    unittest.main()
