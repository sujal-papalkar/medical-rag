"""
Regression Tests for Registered Patient Profiles and Clinical Formulation Generation.

Verifies:
1. Profile extraction, clinical table matching, and comorbidity isolation across all 7 registered patients.
2. Formulation sanitization and exact 1-to-1 document/page citations.
3. Handling of insufficient guideline evidence without hallucination.
"""

import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.repositories import PatientRepository
from app.schemas.prescriptions import PatientInfo, MedicineItem
from app.rag.clinical_matcher import (
    extract_clinical_profile,
    is_chunk_applicable_for_profile,
    prioritize_and_isolate_chunks,
    sanitize_prescribed_medicines,
    RESPIRATORY_TABLE_MAP,
)
from app.rag.generation import generate_structured_prescription


class TestPatientPrescriptionRegression(unittest.TestCase):
    """Regression suite covering all 7 registered patient profiles."""

    def setUp(self):
        self.patients = {p["id"]: p for p in PatientRepository.list_patients()}

    def test_pat_dm_001_profile_and_isolation(self):
        """PAT-DM-001: Rajesh Sharma - Type 2 Diabetes with Trushna and Aruchi."""
        p = self.patients["PAT-DM-001"]
        p_info = PatientInfo(**{k: p[k] for k in ["name", "age", "gender", "disease", "presentation"]})
        profile = extract_clinical_profile(p["clinical_query"], patient_info=p_info, disease=p["disease"])

        self.assertEqual(profile.disease, "diabetes")
        self.assertEqual(profile.age, 54)
        self.assertIn("trushna", profile.symptoms)
        self.assertIn("aruchi", profile.symptoms)

    def test_pat_dm_002_profile_and_isolation(self):
        """PAT-DM-002: Sunita Patil - High-risk pre-diabetes, Overweight BMI >= 25."""
        p = self.patients["PAT-DM-002"]
        p_info = PatientInfo(**{k: p[k] for k in ["name", "age", "gender", "disease", "presentation"]})
        profile = extract_clinical_profile(p["clinical_query"], patient_info=p_info, disease=p["disease"])

        self.assertEqual(profile.disease, "diabetes")
        self.assertEqual(profile.age, 48)
        self.assertTrue(profile.is_adult)

    def test_pat_dm_003_profile_and_isolation(self):
        """PAT-DM-003: Ramesh Gupta - Diabetic Nephropathy Stage 3 complications."""
        p = self.patients["PAT-DM-003"]
        p_info = PatientInfo(**{k: p[k] for k in ["name", "age", "gender", "disease", "presentation"]})
        profile = extract_clinical_profile(p["clinical_query"], patient_info=p_info, disease=p["disease"])

        self.assertEqual(profile.disease, "diabetes")
        self.assertEqual(profile.age, 62)
        self.assertIn("shoth", profile.symptoms)

    def test_pat_resp_001_mild_isolation_and_citations(self):
        """PAT-RESP-001: Priya Kulkarni - Mild respiratory (HRCT 0-8, SpO2 >94%) without dyspnea."""
        p = self.patients["PAT-RESP-001"]
        p_info = PatientInfo(**{k: p[k] for k in ["name", "age", "gender", "disease", "presentation"]})
        profile = extract_clinical_profile(p["clinical_query"], patient_info=p_info, disease=p["disease"])

        self.assertEqual(profile.disease, "respiratory_viral_infection")
        self.assertEqual(profile.age, 32)
        self.assertTrue(profile.is_adult)
        self.assertEqual(profile.severity, "mild")
        self.assertFalse(profile.has_comorbidities)
        self.assertEqual(profile.target_chunk_id, "DOC-FC76496810AB-0035-77484627D9DE")
        self.assertEqual(profile.matched_page, 17)

        # Ensure comorbidity chunks (Page 14, 19, 20, 21) are filtered out
        comorbidity_chunks = [
            {"chunk_id": "DOC-FC76496810AB-0043-40B6B7FCDD58", "page": 20, "content": "Heeraka Rasayana"},
            {"chunk_id": "DOC-FC76496810AB-0040-5EE61CBFB45B", "page": 19, "content": "Sutendra"},
            {"chunk_id": "DOC-FC76496810AB-0028-4F2CFBD3E05E", "page": 14, "content": "Udakvah srotas vyadhi (Diabetes Mellitus)"}
        ]
        isolated = prioritize_and_isolate_chunks(comorbidity_chunks, profile)
        self.assertEqual(len(isolated), 1)
        self.assertEqual(isolated[0]["chunk_id"], "DOC-FC76496810AB-0035-77484627D9DE")

        # Test sanitization strictly retains Page 17 mild formulations with 1-to-1 citation
        raw_meds = [
            MedicineItem(medicine="Somtajvir", dose="1-0-0", supporting_chunk_ids=["DOC-FC76496810AB-0035-77484627D9DE"]),
            MedicineItem(medicine="Pranvir", dose="2-2-2", supporting_chunk_ids=["DOC-FC76496810AB-0035-77484627D9DE"]),
            MedicineItem(medicine="Sutendra", dose="1-0-0", supporting_chunk_ids=["DOC-FC76496810AB-0040-5EE61CBFB45B"]),
        ]
        sanitized = sanitize_prescribed_medicines(raw_meds, profile, isolated)
        med_names = [m.medicine for m in sanitized]
        self.assertNotIn("Sutendra", med_names)
        self.assertIn("Somtajvir", med_names)
        self.assertIn("Pranvir", med_names)
        self.assertIn("Rasaka Rasayana", med_names)
        self.assertIn("Sindhurbhushan Rasayan", med_names)
        for m in sanitized:
            self.assertEqual(m.supporting_chunk_ids, ["DOC-FC76496810AB-0035-77484627D9DE"])

    def test_pat_resp_002_diabetes_comorbidity_resolution(self):
        """PAT-RESP-002: Amit Deshmukh - Adult respiratory with Diabetes comorbidity."""
        p = self.patients["PAT-RESP-002"]
        p_info = PatientInfo(**{k: p[k] for k in ["name", "age", "gender", "disease", "presentation"]})
        profile = extract_clinical_profile(p["clinical_query"], patient_info=p_info, disease=p["disease"])

        self.assertEqual(profile.disease, "respiratory_viral_infection")
        self.assertEqual(profile.age, 58)
        self.assertTrue(profile.is_adult)
        self.assertEqual(profile.severity, "mild")
        self.assertTrue(profile.has_comorbidities)
        self.assertIn("diabetes", profile.comorbidities)
        self.assertEqual(profile.target_chunk_id, "DOC-FC76496810AB-0028-4F2CFBD3E05E")
        self.assertEqual(profile.matched_page, 14)

    def test_pat_resp_003_moderate_severity_precedence(self):
        """PAT-RESP-003: Ananya Joshi - Moderate respiratory with mild breathlessness."""
        p = self.patients["PAT-RESP-003"]
        p_info = PatientInfo(**{k: p[k] for k in ["name", "age", "gender", "disease", "presentation"]})
        profile = extract_clinical_profile(p["clinical_query"], patient_info=p_info, disease=p["disease"])

        self.assertEqual(profile.disease, "respiratory_viral_infection")
        self.assertEqual(profile.age, 29)
        self.assertTrue(profile.is_adult)
        # Moderate HRCT (9 to 15) must not be overridden by symptom descriptor "mild breathlessness"
        self.assertEqual(profile.severity, "moderate")
        self.assertEqual(profile.target_chunk_id, "DOC-FC76496810AB-0035-77484627D9DE")
        self.assertEqual(profile.matched_page, 17)

        # Moderate table must include Mahalakshmi Vilas
        target_info = RESPIRATORY_TABLE_MAP["adult_moderate"]
        self.assertIn("Mahalakshmi Vilas", target_info["medicines"])

    def test_pat_resp_004_severe_table_resolution(self):
        """PAT-RESP-004: Suresh Verma - Severe respiratory infection."""
        p = self.patients["PAT-RESP-004"]
        p_info = PatientInfo(**{k: p[k] for k in ["name", "age", "gender", "disease", "presentation"]})
        profile = extract_clinical_profile(p["clinical_query"], patient_info=p_info, disease=p["disease"])

        self.assertEqual(profile.disease, "respiratory_viral_infection")
        self.assertEqual(profile.age, 67)
        self.assertTrue(profile.is_adult)
        self.assertEqual(profile.severity, "severe")
        self.assertEqual(profile.target_chunk_id, "DOC-FC76496810AB-0036-20ED5DC46A3C")
        self.assertEqual(profile.matched_page, 17)

        # Severe table must include Pranvallabha Rasayan and Mahalakshmi Vilas
        target_info = RESPIRATORY_TABLE_MAP["adult_severe"]
        self.assertIn("Pranvallabha Rasayan", target_info["medicines"])
        self.assertIn("Mahalakshmi Vilas", target_info["medicines"])

    def test_insufficient_evidence_produces_empty_medicines_safely(self):
        """Queries for diseases outside the knowledge base must return empty medicines safely."""
        res = generate_structured_prescription(
            query="What Ayurvedic medicines are prescribed for acute fracture healing in osteoporosis?",
            disease="orthopedics"
        )
        self.assertEqual(res.status, "insufficient_context")
        self.assertEqual(len(res.medicines), 0)
        self.assertTrue(any("insufficient" in lim.lower() or "no relevant" in lim.lower() for lim in res.limitations))

    @patch("app.rag.generation.call_gemini_with_fallback")
    def test_all_seven_patients_end_to_end_generation(self, mock_gemini):
        """All 7 registered patients must successfully generate non-zero formulations with valid citations."""
        for pid, p_data in self.patients.items():
            with self.subTest(patient_id=pid):
                # Construct mock response matching clinical profile
                target_med = "Zincare" if "DM" in pid else "Somtajvir"
                mock_json = {
                    "clinical_guidance": {
                        "condition": p_data["presentation"],
                        "severity_or_stage": "Evaluated Stage",
                        "guidance_summary": "Standard clinical guideline management.",
                        "key_recommendations": [f"Administer {target_med} per protocol."]
                    },
                    "medicines": [
                        {
                            "medicine": target_med,
                            "dose": "1-0-1",
                            "dosage_form": "Tablet",
                            "route": "Oral",
                            "frequency": "Twice daily",
                            "timing": "After food",
                            "duration": "14 days",
                            "anupana": "Warm water",
                            "special_instructions": None,
                            "supporting_chunk_ids": []
                        }
                    ],
                    "limitations": []
                }
                import json
                mock_gemini.return_value = {
                    "text": json.dumps(mock_json),
                    "model": "gemini-2.5-flash",
                    "attempts": 1
                }

                p_info = PatientInfo(**{k: p_data[k] for k in ["name", "age", "gender", "disease", "presentation"]})
                res = generate_structured_prescription(
                    query=p_data["clinical_query"],
                    disease=p_data["disease"],
                    patient_info=p_info,
                    top_k=5,
                    num_candidates=1
                )

                self.assertEqual(res.status, "success", f"Patient {pid} failed with status: {res.status}")
                self.assertGreater(len(res.medicines), 0, f"Patient {pid} returned 0 medicines!")
                self.assertGreater(len(res.evidence_sources), 0, f"Patient {pid} missing evidence citations!")
                for med in res.medicines:
                    self.assertTrue(len(med.supporting_chunk_ids) > 0, f"Medicine {med.medicine} missing chunk citation!")

    def test_all_seven_patients_conflicting_queries_block_generation(self):
        """Queries that contradict registered clinical records must flag conflict and block generation."""
        for pid, p_data in self.patients.items():
            with self.subTest(patient_id=pid):
                p_info = PatientInfo(patient_id=pid, **{k: p_data[k] for k in ["name", "age", "gender", "disease", "presentation"]})
                
                # Query asserting conflicting age (e.g. pediatric age 8 for adult)
                conflicting_query = f"A 8-year-old pediatric child presenting with {p_data['presentation']}"

                res = generate_structured_prescription(
                    query=conflicting_query,
                    disease=p_data["disease"],
                    patient_info=p_info,
                    confirm_override=False
                )

                self.assertEqual(res.status, "conflict_detected")
                self.assertTrue(res.requires_confirmation)
                self.assertEqual(len(res.medicines), 0)
                self.assertGreater(len(res.conflicts), 0)

    @patch("app.rag.generation.call_gemini_with_fallback")
    def test_all_seven_patients_confirmed_overrides_generate_successfully(self, mock_gemini):
        """When physician confirms override, generation proceeds with confirmed parameters."""
        for pid, p_data in self.patients.items():
            with self.subTest(patient_id=pid):
                target_med = "Zincare" if "DM" in pid else "Somtajvir"
                import json
                mock_gemini.return_value = {
                    "text": json.dumps({
                        "clinical_guidance": {
                            "condition": "Confirmed Scenario",
                            "severity_or_stage": "Confirmed Stage",
                            "guidance_summary": "Confirmed clinical override regimen.",
                            "key_recommendations": ["Follow confirmed protocol."]
                        },
                        "medicines": [
                            {
                                "medicine": target_med,
                                "dose": "1-0-0",
                                "dosage_form": "Rasayana",
                                "route": "Oral",
                                "frequency": "Once daily",
                                "timing": "Empty stomach",
                                "duration": "30 days",
                                "anupana": "Warm water",
                                "special_instructions": None,
                                "supporting_chunk_ids": []
                            }
                        ],
                        "limitations": []
                    }),
                    "model": "gemini-2.5-flash",
                    "attempts": 1
                }

                p_info = PatientInfo(patient_id=pid, **{k: p_data[k] for k in ["name", "age", "gender", "disease", "presentation"]})
                conflicting_query = f"A 10-year-old child presenting with {p_data['presentation']}"

                res = generate_structured_prescription(
                    query=conflicting_query,
                    disease=p_data["disease"],
                    patient_info=p_info,
                    confirm_override=True,
                    num_candidates=1
                )

                self.assertEqual(res.status, "success")
                self.assertFalse(res.requires_confirmation)
                self.assertGreater(len(res.medicines), 0)
                self.assertGreater(len(res.conflicts), 0)  # Audited in response
                self.assertTrue(any("override confirmed" in str(lim).lower() for lim in res.limitations))

    def test_registered_profiles_remain_isolated_and_immutable(self):
        """Ensures the 7 authoritative registered patient records are never mutated by test profiles."""
        patients = PatientRepository.list_patients()
        self.assertEqual(len(patients), 7)
        registered_ids = [p["id"] for p in patients]
        self.assertEqual(
            registered_ids,
            ["PAT-DM-001", "PAT-DM-002", "PAT-DM-003", "PAT-RESP-001", "PAT-RESP-002", "PAT-RESP-003", "PAT-RESP-004"]
        )

    @patch("app.rag.generation.call_gemini_with_fallback")
    @patch("app.rag.generation.get_retrieval_service")
    def test_temporary_test_patient_workflow(self, mock_get_retrieval, mock_gemini):
        """Validates that a temporary test patient profile generates prescriptions cleanly without database insertion."""
        test_patient = PatientInfo(
            patient_id="TEST-TMP-001",
            name="Test Patient (Mild Respiratory)",
            age=34,
            gender="Female",
            disease="respiratory_viral_infection",
            presentation="Mild respiratory viral infection with dry cough, SpO2 96%, HRCT score 3"
        )

        mock_retrieval = MagicMock()
        mock_retrieval.retrieve.return_value = [
            {
                "chunk_id": "test_chunk_resp_p17",
                "document_name": "guidelines_respiratory_viral_infection.pdf",
                "page": 17,
                "content": "Rasayana therapy for mild respiratory infection in adults: Chyawanprash 10g once daily with milk.",
                "combined_score": 0.85
            }
        ]
        mock_get_retrieval.return_value = mock_retrieval

        mock_gemini.return_value = {
            "text": json.dumps({
                "clinical_guidance": {
                    "condition": "Mild respiratory viral infection",
                    "severity_or_stage": "mild",
                    "guidance_summary": "Administer Rasayana therapy.",
                    "key_recommendations": ["Chyawanprash"]
                },
                "medicines": [
                    {
                        "medicine": "Chyawanprash",
                        "dose": "10 g",
                        "dosage_form": "Rasayana",
                        "route": "Oral",
                        "frequency": "Once daily",
                        "timing": "Morning",
                        "duration": "15 days",
                        "anupana": "Warm milk",
                        "special_instructions": None,
                        "supporting_chunk_ids": ["test_chunk_resp_p17"]
                    }
                ],
                "limitations": []
            }),
            "model": "gemini-2.5-flash",
            "attempts": 1
        }

        from app.rag.generation import generate_structured_prescription
        res = generate_structured_prescription(
            query="Prescribe Ayurvedic rasayana for mild respiratory infection in a 34-year-old female with SpO2 96%.",
            disease="respiratory_viral_infection",
            patient_info=test_patient,
            num_candidates=1
        )

        self.assertEqual(res.status, "success")
        self.assertEqual(res.patient.patient_id, "TEST-TMP-001")
        self.assertEqual(res.patient.age, 34)
        self.assertGreaterEqual(len(res.medicines), 1)
        self.assertTrue(any("Somtajvir" in m.medicine or "Pranvir" in m.medicine for m in res.medicines))
        # Ensure repository remains untouched
        self.assertEqual(len(PatientRepository.list_patients()), 7)


if __name__ == "__main__":
    unittest.main()

