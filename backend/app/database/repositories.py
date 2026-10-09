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


class PatientRepository:
    """Repository for clinical patient profiles."""

    @staticmethod
    def list_patients() -> List[Dict[str, Any]]:
        return CLINICAL_PATIENTS

    @staticmethod
    def get_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
        for p in CLINICAL_PATIENTS:
            if p["id"] == patient_id:
                return p
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
