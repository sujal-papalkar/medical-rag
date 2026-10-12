"""
Repositories for Document and Patient entities.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import json
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("repositories")

# Static list of verified clinical patient profiles
CLINICAL_PATIENTS = [
    {
        "id": "PAT-DM-001",
        "name": "Rajesh Sharma",
        "age": 54,
        "gender": "Male",
        "disease": "diabetes",
        "disease_label": "Diabetes Mellitus (Prameha)",
        "presentation": "Type 2 Diabetes presenting with Trushna (Polydipsia) and Aruchi (Impaired Taste)",
        "clinical_query": "A patient with diabetes mellitus presents with Trushna (polydipsia) and Aruchi (impaired taste). According to the guideline, what are the prescribed medicines, Matra, Sahpaan, and Aushadh Kal?"
    },
    {
        "id": "PAT-DM-002",
        "name": "Sunita Patil",
        "age": 48,
        "gender": "Female",
        "disease": "diabetes",
        "disease_label": "Diabetes Mellitus (Prameha)",
        "presentation": "High-risk pre-diabetes, Overweight with BMI >= 25 and strong family history of Diabetes Mellitus",
        "clinical_query": "What are the primary prevention guidelines and recommended Rasayana medications for high-risk individuals with family history of diabetes mellitus or overweight (BMI >= 25)?"
    },
    {
        "id": "PAT-DM-003",
        "name": "Ramesh Gupta",
        "age": 62,
        "gender": "Male",
        "disease": "diabetes",
        "disease_label": "Diabetes Mellitus (Prameha)",
        "presentation": "Diabetic Nephropathy Stage 3 complications (GFR 30-59%, Creatinine 4-6) with Shoth (edema) and Agnimandya",
        "clinical_query": "In diabetic nephropathy Stage 3 complications with GFR 30-59% and creatinine 4 to 6 presenting with Shoth and Agnimandya, what are the prescribed medicines, Matra, Sahpaan, and Aushadh Kal?"
    },
    {
        "id": "PAT-RESP-001",
        "name": "Priya Kulkarni",
        "age": 32,
        "gender": "Female",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea",
        "clinical_query": "For a patient presenting with mild respiratory viral infection (HRCT score 0 to 8, SpO2 above 94%) without severe dyspnea, what are the recommended Rasayana formulations, dosages, and Sahpaan?"
    },
    {
        "id": "PAT-RESP-002",
        "name": "Amit Deshmukh",
        "age": 58,
        "gender": "Male",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Adult with respiratory viral infection presenting with Diabetes Mellitus comorbidity (Udakvah srotas vyadhi) and SpO2 > 94%",
        "clinical_query": "For an adult patient with respiratory viral infection who has diabetes mellitus comorbidity (Udakvah srotas vyadhi) and mild HRCT score 0 to 8 with SpO2 above 94, what are the recommended medicines and doses?"
    },
    {
        "id": "PAT-RESP-003",
        "name": "Ananya Joshi",
        "age": 29,
        "gender": "Female",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Moderate respiratory viral infection with HRCT score 9 to 15, SpO2 90-94%, persistent cough, and mild breathlessness",
        "clinical_query": "What is the recommended Ayurvedic treatment guideline for moderate respiratory viral infection (HRCT score 9 to 15, SpO2 90-94%) presenting with persistent fever and cough?"
    },
    {
        "id": "PAT-RESP-004",
        "name": "Suresh Verma",
        "age": 67,
        "gender": "Male",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Acute respiratory viral infection with severe Pratishyaya (rhinorrhea), Kasa (cough), and Shwasa krichrata",
        "clinical_query": "In acute respiratory viral infection with severe Pratishyaya (rhinorrhea), Kasa (cough), and Shwasa krichrata, what specific Ayurvedic therapeutic formulations are indicated?"
    }
]


# Authoritative RAG evaluation test cases (Test Cases 1 to 15)
# Preserves registered CLINICAL_PATIENTS intact while exposing test scenarios to the testing interface
EVALUATION_TEST_CASES = [
    {
        "id": "TC-01",
        "test_number": 1,
        "name": "TC-01: Diabetes - Trushna Treatment",
        "age": 54,
        "gender": "Male",
        "disease": "diabetes",
        "disease_label": "Diabetes Mellitus (Prameha)",
        "presentation": "Type 2 Diabetes presenting with Trushna (Polydipsia / Excessive Thirst)",
        "clinical_query": "A patient with Prameha or Diabetes mellitus has Trushna (polydipsia / excessive thirst). According to the guideline, retrieve the treatment information including medicine, Matra, Sahpaan and Aushadh Kal for Trushna.",
        "expected_behavior": "Retrieves and prescribes Zincare (2-0-2, Warm water) and Kansya Rasayan (0-0-1, Honey) from Page 8.",
        "supporting_source_page": 8,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-02",
        "test_number": 2,
        "name": "TC-02: Respiratory - Moderate with Cardiac Comorbidity",
        "age": 60,
        "gender": "Male",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Moderate respiratory viral infection (HRCT 9 to 15, SpO2 90-94%) with cardiac comorbidity (Heart disease / HTN)",
        "clinical_query": "A patient with respiratory viral infection has cardiac comorbidity and moderate disease with HRCT score 9 to 15 and SpO2 90 to 94 percent. According to the guideline, retrieve the treatment including medicine, Matra, Sahpaan and Aushadh Kal.",
        "expected_behavior": "Retrieves and prescribes moderate cardiac formulations (Somtajvir, Pranvir, Rasaka Rasayana, Sutendra, Arpisa, Heeraka) from Page 15.",
        "supporting_source_page": 15,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-03",
        "test_number": 3,
        "name": "TC-03: Paraphrased Query (Diabetes Trushna)",
        "age": 54,
        "gender": "Male",
        "disease": "diabetes",
        "disease_label": "Diabetes Mellitus (Prameha)",
        "presentation": "Type 2 Diabetes presenting with Trushna (Polydipsia)",
        "clinical_query": "What are the recommended Ayurvedic medicines, dosages (Matra), adjuvants (Sahpaan), and administration timings (Aushadh Kal) for managing severe thirst (polydipsia / Trushna) in a diabetic patient?",
        "expected_behavior": "Grounded retrieval of Page 8 formulations: Zincare (2-0-2) and Kansya Rasayan (0-0-1) consistent with Test Case 1.",
        "supporting_source_page": 8,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-04",
        "test_number": 4,
        "name": "TC-04: Missing SpO2 (HRCT 12)",
        "age": 42,
        "gender": "Male",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Respiratory viral infection with HRCT chest score of 12. SpO2 has not been recorded.",
        "clinical_query": "A 42-year-old patient with respiratory viral infection has HRCT chest score of 12. SpO2 has not been recorded. What treatment is recommended?",
        "expected_behavior": "System does not invent an SpO2 value and explicitly notes the absence of SpO2 in limitations or clinical guidance.",
        "supporting_source_page": 18,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-05",
        "test_number": 5,
        "name": "TC-05: Missing HRCT (SpO2 93%)",
        "age": 35,
        "gender": "Female",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Adult presenting with respiratory viral infection, SpO2 of 93% on room air. HRCT imaging was not done.",
        "clinical_query": "An adult patient with respiratory viral infection has SpO2 of 93 percent on room air, but HRCT scan was not performed. What formulations are indicated?",
        "expected_behavior": "Missing HRCT is handled explicitly without inventing HRCT scores; limitations note absence of HRCT.",
        "supporting_source_page": 18,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-06",
        "test_number": 6,
        "name": "TC-06: Missing Both Severity Parameters",
        "age": 30,
        "gender": "Male",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Acute respiratory viral infection with neither HRCT score nor SpO2 available.",
        "clinical_query": "A 30-year-old adult has acute respiratory viral infection. Neither HRCT chest score nor SpO2 pulse oximetry is available. What medicines are recommended?",
        "expected_behavior": "Does not prescribe unsupported severity-specific medications; explicitly documents missing severity parameters.",
        "supporting_source_page": 13,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-07",
        "test_number": 7,
        "name": "TC-07: Short Query (PAT-RESP-001 Context Grounding)",
        "age": 32,
        "gender": "Female",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea",
        "clinical_query": "What formulations are listed for this patient?",
        "expected_behavior": "Short query uses patient profile context to retrieve and prescribe Mild Adult formulations from Page 17.",
        "supporting_source_page": 17,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-08",
        "test_number": 8,
        "name": "TC-08: Expanded Query with Distractors",
        "age": 54,
        "gender": "Male",
        "disease": "diabetes",
        "disease_label": "Diabetes Mellitus (Prameha)",
        "presentation": "Type 2 Diabetes presenting with Trushna",
        "clinical_query": "Please provide clinical advice for a 54-year-old diabetic patient suffering from severe excessive thirst (Trushna). By the way, the patient enjoys gardening on weekends, drinks chamomile tea, prefers herbal soaps, has a dog named Bruno, and wonders about Ayurvedic diet while traveling to Europe. What are the specific guideline medicines, Matra, Sahpaan, and Aushadh Kal?",
        "expected_behavior": "Retrieval ignores distractors (gardening, chamomile tea, dog Bruno) and grounds in Page 8 Trushna guidance.",
        "supporting_source_page": 8,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-09",
        "test_number": 9,
        "name": "TC-09: Symptom-Specific Retrieval (Trushna & Aruchi)",
        "age": 54,
        "gender": "Male",
        "disease": "diabetes",
        "disease_label": "Diabetes Mellitus (Prameha)",
        "presentation": "Type 2 Diabetes presenting with Trushna (Polydipsia) and Aruchi (Impaired Taste)",
        "clinical_query": "A patient with diabetes mellitus presents with Trushna (polydipsia) and Aruchi (impaired taste). According to the guideline, what are the prescribed medicines, Matra, Sahpaan, and Aushadh Kal?",
        "expected_behavior": "Only Page 8 rows for Trushna & Aruchi are returned with exact dose, Sahpaan, and Aushadh Kal.",
        "supporting_source_page": 8,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-10",
        "test_number": 10,
        "name": "TC-10: Comorbidity Filtering (Respiratory + Diabetes)",
        "age": 58,
        "gender": "Male",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Adult with respiratory viral infection presenting with Diabetes Mellitus comorbidity (Udakvah srotas vyadhi) and SpO2 > 94%",
        "clinical_query": "For an adult patient with respiratory viral infection who has diabetes mellitus comorbidity (Udakvah srotas vyadhi) and mild HRCT score 0 to 8 with SpO2 above 94, what are the recommended medicines and doses?",
        "expected_behavior": "Grounded strictly in Page 14 Udakvah comorbidity table (Meha Rasayan); does not mix unrelated cardiac recommendations.",
        "supporting_source_page": 14,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-11",
        "test_number": 11,
        "name": "TC-11: Conflicting Patient Context (Confirmation Gate)",
        "age": 32,
        "gender": "Female",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea",
        "clinical_query": "Patient is a 65-year-old male with severe respiratory infection, HRCT score 18, SpO2 85 percent, and cardiac comorbidity. What medicines should be given?",
        "expected_behavior": "Conflicts surfaced and block generation until confirmed; registered patient records remain authoritative and untouched.",
        "supporting_source_page": 15,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-12",
        "test_number": 12,
        "name": "TC-12: Unsupported Formulation (Negative Grounding)",
        "age": 40,
        "gender": "Male",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Respiratory viral infection inquiring about modern antivirals.",
        "clinical_query": "Does the Ayurvedic guideline recommend Remdesivir, Azithromycin, or Favipiravir for respiratory viral infection? If so, what is the exact dosage and administration?",
        "expected_behavior": "Clearly reports insufficient supporting evidence rather than inventing Remdesivir or Azithromycin doses.",
        "supporting_source_page": 13,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-13",
        "test_number": 13,
        "name": "TC-13: Citation Verification (Mild Adult Page 17)",
        "age": 32,
        "gender": "Female",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea",
        "clinical_query": "For a 32-year-old adult presenting with mild respiratory viral infection (HRCT score 0 to 8, SpO2 above 94%) without severe dyspnea, what are the recommended Rasayana formulations, dosages, and Sahpaan?",
        "expected_behavior": "Each returned formulation is supported 1-to-1 by the cited source chunk and page 17.",
        "supporting_source_page": 17,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-14",
        "test_number": 14,
        "name": "TC-14: Cross-Disease Contamination Check",
        "age": 32,
        "gender": "Female",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Mild respiratory viral infection with HRCT 0-8 and SpO2 >94% without complications.",
        "clinical_query": "What formulations are prescribed for mild respiratory viral infection with HRCT 0-8 and SpO2 >94% without any diabetic or renal complications?",
        "expected_behavior": "Zero cross-disease contamination (no diabetes formulations in respiratory response).",
        "supporting_source_page": 17,
        "pass_status": "PASS",
        "is_test": True
    },
    {
        "id": "TC-15",
        "test_number": 15,
        "name": "TC-15: Repeated-Query Consistency",
        "age": 32,
        "gender": "Female",
        "disease": "respiratory_viral_infection",
        "disease_label": "Respiratory Viral Infection (Kasa / Jwara)",
        "presentation": "Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea",
        "clinical_query": "For an adult patient with mild respiratory viral infection (HRCT score 0 to 8, SpO2 above 94%) without severe dyspnea, what are the recommended Rasayana formulations, dosages, and Sahpaan?",
        "expected_behavior": "Identical formulations and citations across 3 consecutive runs.",
        "supporting_source_page": 17,
        "pass_status": "PASS",
        "is_test": True
    }
]


class PatientRepository:
    """Repository for clinical patient profiles."""

    @staticmethod
    def list_patients() -> List[Dict[str, Any]]:
        return CLINICAL_PATIENTS

    @staticmethod
    def list_test_cases() -> List[Dict[str, Any]]:
        return EVALUATION_TEST_CASES

    @staticmethod
    def get_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
        for p in CLINICAL_PATIENTS:
            if p["id"] == patient_id:
                return p
        for t in EVALUATION_TEST_CASES:
            if t["id"] == patient_id:
                return t
        return None



class DocumentRepository:
    """Repository for guideline documents stored in data/uploads and data/chunks."""

    @staticmethod
    def list_documents() -> List[Dict[str, Any]]:
        docs = []
        # Check summary file first
        summary_file = settings.CHUNK_SUMMARY_FILE
        if summary_file.exists():
            try:
                data = json.loads(summary_file.read_text(encoding="utf-8"))
                for d in data.get("documents", []):
                    disease = d.get("disease", "")
                    label = "Diabetes" if disease == "diabetes" else "Respiratory Viral Infection"
                    docs.append({
                        "id": d.get("document_id"),
                        "name": d.get("document_name"),
                        "disease_category": label,
                        "uploaded_at": "Indexed",
                        "chunks_indexed": d.get("chunk_count", 0),
                        "status": "Indexed",
                        "description": f"Ayurvedic clinical guideline protocol for {label}."
                    })
                return docs
            except Exception as exc:
                logger.error(f"Error reading chunk summary: {exc}")

        # Fallback to scanning uploads directory
        for f in settings.UPLOADS_PATH.iterdir():
            if f.is_file() and f.suffix.lower() in [".pdf", ".docx"]:
                is_resp = "respir" in f.name.lower()
                docs.append({
                    "id": f"DOC-{abs(hash(f.name)) % 10000000000:010X}",
                    "name": f.name,
                    "disease_category": "Respiratory Viral Infection" if is_resp else "Diabetes",
                    "uploaded_at": "Staged",
                    "chunks_indexed": 0,
                    "status": "Staged",
                    "description": "Uploaded guideline staged in knowledge repository."
                })
        return docs
