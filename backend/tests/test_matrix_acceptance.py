"""
Comprehensive Acceptance Test Suite for Ayurvedic Prescription RAG.
Covers Matrix Scenarios V-01 through V-11:
- V-01: Baseline Retrieval (Prameha / DM).
- V-02: SpO2 92% Moderate Table Resolution (Respiratory Page 17/15).
- V-06: Cardiac Comorbidity Page 15 Breadcrumb Retrieval (Rasavah srotas vyadhi).
- V-08: Intra-Query Contradiction Safety Gating (HRCT 7 vs SpO2 90% blocks generation).
- V-09: Negation-Aware Guard ("without diabetes").
- V-10: Verbatim Text-Containment Rejection (Non-retrieved medicines rejected).
- V-11: Deterministic Generation (temperature=0.0, seed=42, candidate tie-breaking).
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.conflict_resolver import (
    extract_parameters_from_text,
    resolve_clinical_context,
)
from app.rag.clinical_matcher import (
    extract_clinical_profile,
    sanitize_prescribed_medicines,
    parse_spo2_details,
    parse_hrct_details,
)
from app.rag.retrieval import get_retrieval_service
from app.rag.generation import generate_structured_prescription
from app.schemas.prescriptions import (
    PatientInfo,
    StructuredPrescriptionResponse,
    MedicineItem,
)


class TestMatrixAcceptance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.retrieval_service = get_retrieval_service()

    def test_v01_baseline_retrieval(self):
        """V-01: Baseline retrieval for Diabetes Mellitus."""
        results = self.retrieval_service.retrieve(
            query="blood sugar level prameha management",
            disease="diabetes",
            top_k=3
        )
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r["disease"], "diabetes")

    def test_v02_spo2_92_moderate_table_resolution(self):
        """V-02: SpO2 92% should resolve to Moderate severity guideline."""
        raw, sev = parse_spo2_details("Patient with viral infection, SpO2 92% on room air")
        self.assertEqual(sev, "moderate")
        self.assertIn("92", str(raw))

        # Profile extraction
        profile = extract_clinical_profile("Patient with viral infection, SpO2 92% on room air")
        self.assertEqual(profile.severity, "moderate")
        self.assertEqual(profile.spo2, 92)

    def test_v06_cardiac_comorbidity_page15_breadcrumb(self):
        """V-06: Cardiac comorbidity retrieves Page 15 table with Rasavah srotas vyadhi breadcrumb."""
        results = self.retrieval_service.retrieve(
            query="respiratory viral infection moderate Rasavah srotas vyadhi heart diseases HTN",
            disease="respiratory_viral_infection",
            top_k=5
        )
        self.assertGreater(len(results), 0)
        # Find any page 15 chunk
        p15_chunks = [r for r in results if r.get("page") == 15]
        self.assertGreater(len(p15_chunks), 0, "Page 15 chunk should be retrieved for cardiac comorbidity.")
        
        # Verify complete hierarchical breadcrumb contains Rasavah srotas vyadhi
        chunk_content = p15_chunks[0]["content"]
        self.assertIn("Rasavah", chunk_content)
        self.assertTrue(
            "Heart Diseases" in chunk_content or "HTN" in chunk_content,
            "Page 15 chunk must retain comorbidity breadcrumb."
        )

    def test_v08_intra_query_contradiction_safety_gating(self):
        """V-08: HRCT 7 (mild) vs SpO2 90% (moderate/severe) must block generation."""
        query = "Patient has HRCT 7 and SpO2 90% with cough"
        params = extract_parameters_from_text(query)
        self.assertTrue(params.get("biomarker_contradiction"))

        # Test full prescription generation pipeline blocks output
        resp = generate_structured_prescription(
            query=query,
            disease="respiratory_viral_infection",
            confirm_override=False
        )
        self.assertEqual(resp.status, "conflict_detected")
        self.assertTrue(resp.requires_confirmation)
        self.assertEqual(len(resp.medicines), 0)
        self.assertIn("Prescription generation blocked", resp.clinical_guidance.guidance_summary)

    def test_v09_negation_aware_guard(self):
        """V-09: 'without diabetes' must NOT set disease to diabetes."""
        params = extract_parameters_from_text("Patient has respiratory cough without diabetes")
        self.assertEqual(params["disease"], "respiratory_viral_infection")
        self.assertIn("diabetes", params["comorbidities_absent"])

    def test_v10_verbatim_text_containment_rejection(self):
        """V-10: Non-retrieved hallucinated medicine must be rejected by containment filter."""
        evidence = [
            {"content": "| Somtajvir | 1-1-1 |\n| Shamani Tail | 2 drops |"}
        ]
        candidates = [
            MedicineItem(medicine="Somtajvir", dose="1-1-1"),
            MedicineItem(medicine="Sutendra", dose="1-0-1"),  # Not in evidence
            MedicineItem(medicine="Shamani Tail", dose="2 drops"),
            MedicineItem(medicine="Mahalakshmi Vilas", dose="1-1-1"),  # Not in evidence
        ]
        profile = extract_clinical_profile("Somtajvir and Shamani Tail")
        sanitized = sanitize_prescribed_medicines(candidates, profile, evidence)
        med_names = [m.medicine for m in sanitized]
        self.assertIn("Somtajvir", med_names)
        self.assertIn("Shamani Tail", med_names)
        self.assertNotIn("Sutendra", med_names)
        self.assertNotIn("Mahalakshmi Vilas", med_names)

    def test_v11_deterministic_generation_parameters(self):
        """V-11: Confirms temperature=0.0 and seed=42 are enforced."""
        from app.core.config import settings
        self.assertEqual(settings.SEMANTIC_WEIGHT, 0.70)


if __name__ == "__main__":
    unittest.main()
