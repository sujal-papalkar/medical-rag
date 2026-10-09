"""
Parameterized Unit Test Suite for Universal Clinical Conflict Resolution.

Verifies:
1. Matching cases across diabetes, respiratory, and comorbidity patients (no conflicts).
2. Conflicting cases: demographics (age, category), disease category, comorbidity discrepancy,
   active comorbidity negation, and severity/biomarker contradictions.
3. Missing data handling: queries omitting age, severity, or comorbidity do not trigger false conflicts.
4. Confirmed physician overrides: query scenario takes precedence for retrieval without modifying database.
5. Generation guardrails: unconfirmed conflicts return status="conflict_detected" with empty medicines.
6. Universal applicability: rules apply cleanly without hardcoding patient IDs or medicine names.
"""

import unittest
from unittest.mock import patch, MagicMock

from app.schemas.prescriptions import PatientInfo, StructuredPrescriptionResponse
from app.database.repositories import PatientRepository
from app.rag.conflict_resolver import (
    extract_parameters_from_text,
    extract_parameters_from_patient,
    detect_clinical_conflicts,
    resolve_clinical_context,
)
from app.rag.generation import generate_structured_prescription


class TestParameterExtraction(unittest.TestCase):
    """Tests parameter extraction from arbitrary clinical query strings."""

    def test_extract_age_and_category(self):
        text_adult = "A 45-year-old patient presenting with fever"
        params_adult = extract_parameters_from_text(text_adult)
        self.assertEqual(params_adult["age"], 45)
        self.assertTrue(params_adult["is_adult"])

        text_pediatric = "A 9-year-old child presenting with cough"
        params_peds = extract_parameters_from_text(text_pediatric)
        self.assertEqual(params_peds["age"], 9)
        self.assertFalse(params_peds["is_adult"])

    def test_extract_severity_and_biomarkers(self):
        text_mild = "Mild respiratory viral infection with HRCT 0-8 and SpO2 >94%"
        params_mild = extract_parameters_from_text(text_mild)
        self.assertEqual(params_mild["severity"], "mild")

        text_mod = "Moderate respiratory infection with HRCT 9-15 and SpO2 90-94%"
        params_mod = extract_parameters_from_text(text_mod)
        self.assertEqual(params_mod["severity"], "moderate")

        text_sev = "Severe viral infection with HRCT >15 and SpO2 <90%"
        params_sev = extract_parameters_from_text(text_sev)
        self.assertEqual(params_sev["severity"], "severe")

    def test_extract_comorbidities_and_negations(self):
        text_comorb = "Patient with diabetes mellitus comorbidity and hypertension"
        params = extract_parameters_from_text(text_comorb)
        self.assertIn("diabetes", params["comorbidities_present"])
        self.assertIn("cardiac", params["comorbidities_present"])

        text_negated = "A patient without diabetes and no renal disease"
        params_neg = extract_parameters_from_text(text_negated)
        self.assertIn("diabetes", params_neg["comorbidities_absent"])
        self.assertIn("renal", params_neg["comorbidities_absent"])


class TestMatchingCases(unittest.TestCase):
    """Tests that matching queries for all registered patients produce ZERO conflicts."""

    def test_all_registered_patients_default_queries_match(self):
        patients = PatientRepository.list_patients()
        self.assertGreater(len(patients), 0)

        for p_data in patients:
            with self.subTest(patient_id=p_data["id"]):
                patient = PatientInfo(
                    patient_id=p_data["id"],
                    name=p_data["name"],
                    age=p_data["age"],
                    gender=p_data["gender"],
                    disease=p_data["disease"],
                    presentation=p_data["presentation"]
                )
                query = p_data["clinical_query"]

                result, profile = resolve_clinical_context(
                    query=query,
                    patient_info=patient,
                    disease=p_data["disease"],
                    confirm_override=False
                )

                self.assertFalse(
                    result.requires_confirmation,
                    f"Patient {p_data['id']} falsely flagged conflicts: {result.conflicts}"
                )
                self.assertFalse(result.has_conflict)
                self.assertEqual(len(result.conflicts), 0)


class TestConflictingCases(unittest.TestCase):
    """Parameterized tests for detecting clinical parameter conflicts."""

    def setUp(self):
        # Base adult mild respiratory patient (authoritative record)
        self.resp_patient = PatientInfo(
            patient_id="PAT-RESP-TEST",
            name="Test Respiratory Patient",
            age=34,
            gender="Female",
            disease="respiratory_viral_infection",
            presentation="Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea"
        )
        # Base diabetes patient (authoritative record)
        self.dm_patient = PatientInfo(
            patient_id="PAT-DM-TEST",
            name="Test Diabetes Patient",
            age=55,
            gender="Male",
            disease="diabetes",
            presentation="Type 2 Diabetes presenting with Trushna (Polydipsia) and Aruchi (Impaired Taste)"
        )
        # Base diabetic nephropathy patient (renal comorbidity)
        self.renal_patient = PatientInfo(
            patient_id="PAT-DM-RENAL-TEST",
            name="Test Renal Patient",
            age=62,
            gender="Male",
            disease="diabetes",
            presentation="Diabetic Nephropathy Stage 3 complications (GFR 30-59%, Creatinine 4-6) with Shoth"
        )

    def test_demographic_age_mismatch(self):
        # Query specifies pediatric age 10 for a 34-year-old registered adult
        query = "A 10-year-old child presenting with mild respiratory viral infection (HRCT 0-8, SpO2 >94%)"
        result, _ = resolve_clinical_context(query, self.resp_patient, confirm_override=False)

        self.assertTrue(result.requires_confirmation)
        self.assertTrue(result.has_conflict)
        param_names = [c.parameter for c in result.conflicts]
        self.assertIn("age", param_names)
        self.assertIn("age_category", param_names)

    def test_disease_category_mismatch_dm_to_resp(self):
        # Query asks for respiratory viral infection for a diabetes patient
        query = "What is the recommended Ayurvedic treatment for respiratory viral infection with cough and fever?"
        result, _ = resolve_clinical_context(query, self.dm_patient, confirm_override=False)

        self.assertTrue(result.requires_confirmation)
        param_names = [c.parameter for c in result.conflicts]
        self.assertIn("disease", param_names)
        self.assertEqual(result.conflicts[0].conflict_type, "disease_mismatch")

    def test_disease_category_mismatch_resp_to_dm(self):
        # Query asks for diabetes guidelines for a pure respiratory patient without diabetes
        query = "A patient with diabetes mellitus presents with Trushna and Aruchi, what are the prescribed medicines?"
        result, _ = resolve_clinical_context(query, self.resp_patient, confirm_override=False)

        self.assertTrue(result.requires_confirmation)
        param_names = [c.parameter for c in result.conflicts]
        self.assertIn("disease", param_names)

    def test_unregistered_comorbidity_discrepancy(self):
        # Query specifies diabetes comorbidity on a patient with no registered diabetes
        query = "For a patient presenting with mild respiratory viral infection and diabetes mellitus comorbidity (Udakvah), what are the medicines?"
        result, _ = resolve_clinical_context(query, self.resp_patient, confirm_override=False)

        self.assertTrue(result.requires_confirmation)
        conflict_types = [c.conflict_type for c in result.conflicts]
        self.assertIn("comorbidity_discrepancy", conflict_types)
        comorb_conflict = next(c for c in result.conflicts if c.parameter == "comorbidity")
        self.assertEqual(comorb_conflict.query_value, "diabetes")

    def test_active_comorbidity_negation(self):
        # Query negates active renal comorbidity for diabetic nephropathy patient
        query = "For a patient with diabetes without renal disease presenting with Trushna, what are the guidelines?"
        result, _ = resolve_clinical_context(query, self.renal_patient, confirm_override=False)

        self.assertTrue(result.requires_confirmation)
        comorb_conflict = next(c for c in result.conflicts if c.parameter == "comorbidity")
        self.assertIn("renal", str(comorb_conflict.registered_value))
        self.assertIn("Negated", str(comorb_conflict.query_value))

    def test_severity_contradiction_mild_to_severe(self):
        # Mild patient queried as severe HRCT >15
        query = "For a patient with severe respiratory viral infection (HRCT score >15, SpO2 below 90), what are the formulations?"
        result, _ = resolve_clinical_context(query, self.resp_patient, confirm_override=False)

        self.assertTrue(result.requires_confirmation)
        sev_conflict = next(c for c in result.conflicts if c.parameter == "severity")
        self.assertEqual(sev_conflict.registered_value, "mild")
        self.assertEqual(sev_conflict.query_value, "severe")


class TestMissingDataHandling(unittest.TestCase):
    """Tests that missing query parameters gracefully fall back to authoritative patient data without conflicts."""

    def setUp(self):
        self.patient = PatientInfo(
            patient_id="PAT-RESP-001",
            name="Priya Kulkarni",
            age=32,
            gender="Female",
            disease="respiratory_viral_infection",
            presentation="Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea"
        )

    def test_missing_age_in_query_no_conflict(self):
        # Query specifies symptoms and disease, but omits age
        query = "What are the recommended Rasayana formulations for mild respiratory viral infection with HRCT 0-8?"
        result, profile = resolve_clinical_context(query, self.patient, confirm_override=False)

        self.assertFalse(result.requires_confirmation)
        self.assertEqual(profile.age, 32)
        self.assertTrue(profile.is_adult)

    def test_missing_severity_in_query_no_conflict(self):
        # Query specifies general respiratory inquiry without severity or HRCT score
        query = "For a patient with respiratory viral infection, what are the primary preventive guidelines?"
        result, profile = resolve_clinical_context(query, self.patient, confirm_override=False)

        self.assertFalse(result.requires_confirmation)
        self.assertEqual(profile.severity, "mild")

    def test_autonomous_custom_query_no_patient(self):
        # Custom query submitted without selecting a patient profile
        query = "In diabetic nephropathy Stage 3 complications with GFR 30-59%, what are the prescribed medicines?"
        result, profile = resolve_clinical_context(query, patient_info=None, disease="diabetes", confirm_override=False)

        self.assertFalse(result.requires_confirmation)
        self.assertEqual(profile.disease, "diabetes")


class TestConfirmedOverride(unittest.TestCase):
    """Tests behavior when physician explicitly confirms clinical override."""

    def setUp(self):
        self.resp_patient = PatientInfo(
            patient_id="PAT-RESP-TEST",
            name="Test Patient",
            age=34,
            gender="Female",
            disease="respiratory_viral_infection",
            presentation="Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea"
        )

    def test_confirmed_override_permits_generation(self):
        # Physician intentionally queries severe scenario on a mild patient
        query = "For a patient presenting with severe respiratory viral infection (HRCT >15, SpO2 <90), what is the regimen?"
        result, profile = resolve_clinical_context(query, self.resp_patient, confirm_override=True)

        # Requires confirmation must be False because physician confirmed
        self.assertFalse(result.requires_confirmation)
        # Conflict is logged in audit trail
        self.assertTrue(result.has_conflict)
        self.assertGreater(len(result.conflicts), 0)
        # Profile adopts confirmed clinical scenario
        self.assertEqual(profile.severity, "severe")
        # Registered patient record in object remains unchanged
        self.assertEqual(self.resp_patient.age, 34)
        self.assertEqual(self.resp_patient.disease, "respiratory_viral_infection")


class TestGenerationGuardrails(unittest.TestCase):
    """Tests that unconfirmed conflicts block prescription generation at the entry point."""

    def test_unconfirmed_conflict_blocks_generation(self):
        patient = PatientInfo(
            patient_id="PAT-RESP-001",
            name="Priya Kulkarni",
            age=32,
            gender="Female",
            disease="respiratory_viral_infection",
            presentation="Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea"
        )
        # Conflicting query: severe HRCT >15
        query = "For a patient presenting with severe respiratory viral infection (HRCT score >15, SpO2 <90), what are the medicines?"

        response = generate_structured_prescription(
            query=query,
            disease="respiratory_viral_infection",
            patient_info=patient,
            confirm_override=False
        )

        self.assertEqual(response.status, "conflict_detected")
        self.assertEqual(response.validation_status, "conflict_pending_confirmation")
        self.assertTrue(response.requires_confirmation)
        self.assertEqual(len(response.medicines), 0)
        self.assertGreater(len(response.conflicts), 0)
        self.assertIn("severity", response.limitations[0].lower())


if __name__ == "__main__":
    unittest.main()
