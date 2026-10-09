"""
Unit tests for Clinical Matcher and Table Resolution Engine.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.prescriptions import PatientInfo, MedicineItem
from app.rag.clinical_matcher import (
    extract_clinical_profile,
    is_chunk_applicable_for_profile,
    prioritize_and_isolate_chunks,
    sanitize_prescribed_medicines,
    RESPIRATORY_TABLE_MAP,
)


class TestClinicalMatcher(unittest.TestCase):

    def test_extract_34yo_mild_respiratory_profile(self):
        query = (
            "For a 34-year-old with mild respiratory viral infection (HRCT 0-8, SpO2 >94%), "
            "what are the recommended medicines, Matra, Sahpaan, and Aushadh Kal?"
        )
        profile = extract_clinical_profile(query)
        self.assertEqual(profile.age, 34)
        self.assertTrue(profile.is_adult)
        self.assertEqual(profile.severity, "mild")
        self.assertFalse(profile.has_comorbidities)
        self.assertEqual(profile.comorbidities, [])
        self.assertEqual(profile.matched_page, 17)
        self.assertEqual(profile.target_chunk_id, "DOC-FC76496810AB-0035-77484627D9DE")

    def test_extract_pediatric_profile(self):
        query = "What are the prophylactic Rasayana guidelines for an 8-year-old child with respiratory viral infection risk?"
        profile = extract_clinical_profile(query)
        self.assertEqual(profile.age, 8)
        self.assertFalse(profile.is_adult)
        self.assertEqual(profile.matched_page, 16)

    def test_extract_diabetic_comorbidity_profile(self):
        query = (
            "For an adult patient with respiratory viral infection who has diabetes mellitus comorbidity "
            "(Udakvah srotas vyadhi) and mild HRCT score 0 to 8 with SpO2 above 94, what are the recommended medicines and doses?"
        )
        profile = extract_clinical_profile(query)
        self.assertTrue(profile.is_adult)
        self.assertTrue(profile.has_comorbidities)
        self.assertIn("diabetes", profile.comorbidities)

    def test_is_chunk_applicable_adult_mild_filters_comorbidities(self):
        query = "For a 34-year-old with mild respiratory viral infection (HRCT 0-8, SpO2 >94%)"
        profile = extract_clinical_profile(query)

        # Page 17 chunk (Adult pure respiratory mild/moderate) -> Should be applicable
        chunk_page_17 = {
            "chunk_id": "DOC-FC76496810AB-0035-77484627D9DE",
            "page": 17,
            "section": "RASAYANA GUIDELINES FOR RESPIRATORY VIRAL INFECTION AS PER CT SCORE/ DISEASE SEVERITY ALONG WITH OTHER CO MORBIDITIES",
            "content": "Sub-subsection: Pranvah Srotas vyadhi (Above 15 Years)\n| MILD (0 to 8) SpO2 above 94 | Somtajvir | 1-0-0 |"
        }
        is_app, reason = is_chunk_applicable_for_profile(chunk_page_17, profile)
        self.assertTrue(is_app)

        # Page 19 chunk (Contains Sutendra for diabetes comorbidity) -> Should NOT be applicable
        chunk_page_19 = {
            "chunk_id": "DOC-FC76496810AB-0040-5EE61CBFB45B",
            "page": 19,
            "section": "RASAYANA GUIDELINES FOR RESPIRATORY VIRAL INFECTION AS PER CT SCORE/ DISEASE SEVERITY ALONG WITH OTHER CO MORBIDITIES",
            "content": "| MILD (0 to 8) SpO2 above 94 | Sutendra | 1-0-0 | with honey/warm water |"
        }
        is_app, reason = is_chunk_applicable_for_profile(chunk_page_19, profile)
        self.assertFalse(is_app)
        self.assertIn("Diabetes", reason)

        # Page 20 chunk (Contains Heeraka Rasayana for renal comorbidity) -> Should NOT be applicable
        chunk_page_20 = {
            "chunk_id": "DOC-FC76496810AB-0043-40B6B7FCDD58",
            "page": 20,
            "section": "RASAYANA GUIDELINES FOR RESPIRATORY VIRAL INFECTION AS PER CT SCORE/ DISEASE SEVERITY ALONG WITH OTHER CO MORBIDITIES",
            "content": "| MILD (0 to 8) SpO2 above 94 | Heeraka Rasayana | 1-0-0 |"
        }
        is_app, reason = is_chunk_applicable_for_profile(chunk_page_20, profile)
        self.assertFalse(is_app)
        self.assertIn("Renal", reason)

        # Page 16 chunk (Pediatric <15 years) -> Should NOT be applicable for 34yo adult
        chunk_page_16 = {
            "chunk_id": "DOC-FC76496810AB-0033-312CE552D1E5",
            "page": 16,
            "section": "RASAYANA GUIDELINES FOR RESPIRATORY VIRAL INFECTION AS PER CT SCORE/ DISEASE SEVERITY ALONG WITH OTHER CO MORBIDITIES",
            "content": "Sub-subsection: Pranvah Srotas vyadhi (Below 15 Years)\n| Bal Rasayana | 1-0-0 |"
        }
        is_app, reason = is_chunk_applicable_for_profile(chunk_page_16, profile)
        self.assertFalse(is_app)
        self.assertIn("pediatric", reason)

    def test_sanitize_prescribed_medicines_adult_mild(self):
        query = "For a 34-year-old with mild respiratory viral infection (HRCT 0-8, SpO2 >94%)"
        profile = extract_clinical_profile(query)

        evidence_chunks = [
            {
                "chunk_id": "DOC-FC76496810AB-0035-77484627D9DE",
                "page": 17,
                "content": "Sub-subsection: Pranvah Srotas vyadhi (Above 15 Years)\n| MILD (0 to 8) SpO2 above 94 | Somtajvir | 1-0-0 | Pranvir | 2-2-2 | Rasaka Rasayana | 1-0-1 | Sindhurbhushan Rasayan | 1-0-0 |"
            }
        ]

        # Simulating candidate output where LLM mixed in comorbidity and moderate medicines
        raw_medicines = [
            MedicineItem(medicine="Somtajvir", dose="1-0-0", timing="Rasayan kal", supporting_chunk_ids=["DOC-FC76496810AB-0035-77484627D9DE", "DOC-FC76496810AB-0040-5EE61CBFB45B"]),
            MedicineItem(medicine="Pranvir", dose="2-2-2", timing="After food", supporting_chunk_ids=["DOC-FC76496810AB-0035-77484627D9DE"]),
            MedicineItem(medicine="Sutendra", dose="1-0-0", timing="Rasayan kal", supporting_chunk_ids=["DOC-FC76496810AB-0040-5EE61CBFB45B"]),
            MedicineItem(medicine="Heeraka Rasayana", dose="1-0-0", timing="Rasayan kal", supporting_chunk_ids=["DOC-FC76496810AB-0043-40B6B7FCDD58"]),
            MedicineItem(medicine="Mahalakshmi Vilas", dose="0-0-1", timing="Nisha kal", supporting_chunk_ids=["DOC-FC76496810AB-0035-77484627D9DE"])
        ]

        sanitized = sanitize_prescribed_medicines(raw_medicines, profile, evidence_chunks)
        med_names = [m.medicine for m in sanitized]

        # Sutendra and Heeraka Rasayana must be completely removed
        self.assertNotIn("Sutendra", med_names)
        self.assertNotIn("Heeraka Rasayana", med_names)
        self.assertNotIn("Mahalakshmi Vilas", med_names)

        # Exact adult mild medicines must be present
        self.assertIn("Somtajvir", med_names)
        self.assertIn("Pranvir", med_names)
        self.assertIn("Rasaka Rasayana", med_names)
        self.assertIn("Sindhurbhushan Rasayan", med_names)

        # Supporting chunk ID must strictly be Page 17 chunk only!
        for m in sanitized:
            self.assertEqual(m.supporting_chunk_ids, ["DOC-FC76496810AB-0035-77484627D9DE"])


if __name__ == "__main__":
    unittest.main()
