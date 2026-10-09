"""
Clinical Context Matching and Table Resolution Engine.

Responsible for:
1. Extracting patient clinical parameters (age, adult/pediatric category, HRCT score,
   SpO2, symptoms, disease severity, and explicit comorbidities) from queries and patient records.
2. Matching the patient profile to the authoritative Ayurvedic guideline table before generation.
3. Prioritizing matching guideline chunks and isolating comorbidity/pediatric sections
   when not clinically applicable.
4. Validating and sanitizing candidate medicines to ensure Matra, Sahpaan, Aushadh Kal,
   and exact document/page citations are strictly derived from the matched table.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.schemas.prescriptions import PatientInfo, MedicineItem

logger = get_logger("clinical-matcher")


@dataclass
class ClinicalProfile:
    """Clinical parameters extracted from patient context and clinical queries."""
    disease: Optional[str] = None
    age: Optional[int] = None
    is_adult: Optional[bool] = None        # True if >= 15 years, False if < 15 years, None if unspecified
    severity: Optional[str] = None        # "mild", "moderate", "severe"
    hrct_score_raw: Optional[str] = None  # e.g. "0-8", "0 to 8", "9-15", ">15"
    spo2_raw: Optional[str] = None        # e.g. ">94", "above 94", "90-94", "<90"
    comorbidities: List[str] = field(default_factory=list)
    has_comorbidities: bool = False
    symptoms: List[str] = field(default_factory=list)
    matched_table_name: Optional[str] = None
    matched_page: Optional[int] = None
    target_chunk_id: Optional[str] = None
    table_isolation_reason: Optional[str] = None


# Authoritative mapping of respiratory viral infection rasayana tables
RESPIRATORY_TABLE_MAP = {
    "adult_mild": {
        "page": 17,
        "chunk_id": "DOC-FC76496810AB-0035-77484627D9DE",
        "section": "Pranvah Srotas vyadhi (Above 15 Years)",
        "severity": "MILD (0 to 8) SpO2 above 94",
        "medicines": ["Somtajvir", "Pranvir", "Rasaka Rasayana", "Sindhurbhushan Rasayan"],
        "doses": {"Somtajvir": "1-0-0", "Pranvir": "2-2-2", "Rasaka Rasayana": "1-0-1", "Sindhurbhushan Rasayan": "1-0-0"},
        "sahpaan": {
            "Somtajvir": "with honey/ warm water",
            "Pranvir": "with warm water",
            "Rasaka Rasayana": "with honey /warm water",
            "Sindhurbhushan Rasayan": "with honey/warm water"
        },
        "timing": {
            "Somtajvir": "Rasayan kal (Early morning on empty stomach)",
            "Pranvir": "Three times a day after food",
            "Rasaka Rasayana": "Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime)",
            "Sindhurbhushan Rasayan": "Rasayan kal (Early morning on empty stomach)"
        }
    },
    "adult_moderate": {
        "page": 17,
        "chunk_id": "DOC-FC76496810AB-0035-77484627D9DE",
        "section": "Pranvah Srotas vyadhi (Above 15 Years)",
        "severity": "MODERATE (9 to 15) SpO2 90 to 94",
        "medicines": ["Somtajvir", "Pranvir", "Rasaka Rasayana", "Sindhurbhushan Rasayan", "Mahalakshmi Vilas"],
        "doses": {
            "Somtajvir": "1-0-1",
            "Pranvir": "2-2-2",
            "Rasaka Rasayana": "1-0-1",
            "Sindhurbhushan Rasayan": "1-0-0",
            "Mahalakshmi Vilas": "0-0-1"
        },
        "sahpaan": {
            "Somtajvir": "with honey/ warm water",
            "Pranvir": "with warm water",
            "Rasaka Rasayana": "with honey /warm water",
            "Sindhurbhushan Rasayan": "with honey/ warm water",
            "Mahalakshmi Vilas": "with honey/ warm water"
        },
        "timing": {
            "Somtajvir": "Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime)",
            "Pranvir": "Three times a day after food",
            "Rasaka Rasayana": "Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime)",
            "Sindhurbhushan Rasayan": "Rasayan kal (Early morning on empty stomach)",
            "Mahalakshmi Vilas": "Nisha kal (at bedtime)"
        }
    },
    "adult_severe": {
        "page": 17,
        "chunk_id": "DOC-FC76496810AB-0036-20ED5DC46A3C",
        "section": "Pranvah Srotas vyadhi (Above 15 Years)",
        "severity": "SEVERE (>15) SpO2 below 90",
        "medicines": ["Somtajvir", "Pranvir", "Rasaka Rasayana", "Sindhurbhushan Rasayan", "Mahalakshmi Vilas", "Pranvallabha Rasayan"],
        "doses": {
            "Somtajvir": "1-1-1",
            "Pranvir": "2-2-2",
            "Rasaka Rasayana": "1-0-1",
            "Sindhurbhushan Rasayan": "1-0-0",
            "Mahalakshmi Vilas": "0-0-1",
            "Pranvallabha Rasayan": "1-0-0"
        },
        "sahpaan": {
            "Somtajvir": "with honey/ warm water",
            "Pranvir": "with warm water",
            "Rasaka Rasayana": "with honey /warm water",
            "Sindhurbhushan Rasayan": "with honey/ warm water",
            "Mahalakshmi Vilas": "with honey/warm water",
            "Pranvallabha Rasayan": "with honey/ warm water"
        },
        "timing": {
            "Somtajvir": "Rasayan kal and Vyanodaan kal (Early morning on empty stomach and after lunch and dinner)",
            "Pranvir": "Three times a day after food",
            "Rasaka Rasayana": "Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime)",
            "Sindhurbhushan Rasayan": "Rasayan kal (Early morning on empty stomach)",
            "Mahalakshmi Vilas": "Nisha kal (at bedtime)",
            "Pranvallabha Rasayan": "Rasayan kal (Early morning on empty stomach)"
        }
    },
    "resp_diabetes_mild": {
        "page": 14,
        "chunk_id": "DOC-FC76496810AB-0028-4F2CFBD3E05E",
        "section": "Udakvah srotas vyadhi (Diabetes Mellitus)",
        "severity": "MILD (0 to 8) SpO2 above 94",
        "medicines": ["Somtajvir", "Pranvir", "Rasaka Rasayana", "Meha Rasayan"],
        "doses": {
            "Somtajvir": "1-0-0",
            "Pranvir": "2-2-2",
            "Rasaka Rasayana": "1-0-1",
            "Meha Rasayan": "1-0-0"
        },
        "sahpaan": {
            "Somtajvir": "Honey/Warm water",
            "Pranvir": "Warm water",
            "Rasaka Rasayana": "Honey/Warm water",
            "Meha Rasayan": "Honey/Warm water"
        },
        "timing": {
            "Somtajvir": "Rasayan kal (Early morning on empty stomach)",
            "Pranvir": "Three times a day after food",
            "Rasaka Rasayana": "Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime)",
            "Meha Rasayan": "Rasayan kal (Early morning on empty stomach)"
        }
    },
    "pediatric_all": {
        "page": 16,
        "chunk_id": "DOC-FC76496810AB-0033-312CE552D1E5",
        "section": "Pranvah Srotas vyadhi (Below 15 Years)",
        "medicines": ["Somtajvir", "Rasvir", "Bal Rasayana"],
        "doses": {
            "Somtajvir": "1-0-0",
            "Rasvir": "1-0-1",
            "Bal Rasayana": "1-0-0"
        },
        "sahpaan": {
            "Somtajvir": "with honey/ warm water",
            "Rasvir": "with honey/ warm water",
            "Bal Rasayana": "with honey/ warm water"
        },
        "timing": {
            "Somtajvir": "Rasayan kal (Early morning on empty stomach)",
            "Rasvir": "Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime)",
            "Bal Rasayana": "Rasayan kal (Early morning on empty stomach)"
        }
    }
}


def extract_clinical_profile(
    query: str,
    patient_info: Optional[PatientInfo] = None,
    disease: Optional[str] = None
) -> ClinicalProfile:
    """
    Extracts structured clinical parameters from query text and patient info.
    """
    text_corpus = f"{query} {patient_info.presentation if patient_info and patient_info.presentation else ''}"
    lower = text_corpus.lower()

    profile = ClinicalProfile()
    profile.disease = disease or (patient_info.disease if patient_info else None)
    if not profile.disease:
        if any(w in lower for w in ["respiratory", "viral", "cough", "kasa", "jwara", "hrct", "spo2", "pranvah"]):
            profile.disease = "respiratory_viral_infection"
        elif any(w in lower for w in ["diabetes", "prameha", "sugar", "glucose", "hba1c", "nephropathy"]):
            profile.disease = "diabetes"

    # 1. Extract Age
    if patient_info and patient_info.age is not None:
        profile.age = patient_info.age
        profile.is_adult = patient_info.age >= 15
    else:
        age_match = re.search(r'\b(\d{1,3})\s*(?:-| )(?:year|yr)s?(?:-| )(?:old)?\b|\bage[ :]+(\d{1,3})\b', lower)
        if age_match:
            raw_age = int(age_match.group(1) or age_match.group(2))
            profile.age = raw_age
            profile.is_adult = raw_age >= 15
        elif any(w in lower for w in ["adult", "above 15", "geriatric", "elderly"]):
            profile.is_adult = True
        elif any(w in lower for w in ["child", "children", "pediatric", "below 15", "under 15", "bal"]):
            profile.is_adult = False

    # 2. Extract HRCT Score and SpO2
    hrct_match = re.search(r'hrct\s*(?:score)?\s*(?:of)?\s*([0-9\-\>\<\s]+|greater than \d+|less than \d+)', lower)
    if hrct_match:
        profile.hrct_score_raw = hrct_match.group(1).strip()

    spo2_match = re.search(r'spo2\s*(?:of)?\s*([><]?\s*\d{1,3}%?|\d{1,3}\s*(?:to|-)\s*\d{1,3}%?|above \d+|below \d+)', lower)
    if spo2_match:
        profile.spo2_raw = spo2_match.group(1).strip()

    # 3. Determine Severity: prioritize objective clinical biomarkers (HRCT, SpO2) first, then qualified terms
    if any(w in lower for w in ["hrct >15", "hrct > 15", "greater than 15", "spo2 <90", "spo2 below 90", "below 90"]):
        profile.severity = "severe"
    elif any(w in lower for w in ["hrct 9-15", "hrct 9–15", "hrct 9 to 15", "9 to 15", "spo2 90-94", "spo2 90 to 94", "90 to 94"]):
        profile.severity = "moderate"
    elif any(w in lower for w in ["hrct 0-8", "hrct 0–8", "hrct 0 to 8", "0 to 8", "spo2 >94", "spo2 above 94", "above 94"]):
        profile.severity = "mild"
    elif "moderate" in lower and not re.search(r'\b(?:without|no)\s+moderate\b', lower):
        profile.severity = "moderate"
    elif "severe" in lower and not re.search(r'\b(?:without|no)\s+severe\b', lower):
        profile.severity = "severe"
    elif "mild" in lower and not re.search(r'\b(?:without|no)\s+mild\b', lower):
        profile.severity = "mild"

    # 4. Extract Explicit Comorbidities
    comorbidities = []
    # Check if user explicitly stated "no comorbidity" / "without comorbidity"
    no_comorbidity = bool(re.search(r'\b(?:no|without|zero|free of)\s+(?:known\s+)?(?:comorbidit|co-morbidit|co morbidit)', lower))

    if not no_comorbidity:
        if any(w in lower for w in ["diabetes", "prameha", "udakvah", "high blood sugar", "type 2"]):
            # For respiratory infection queries, only count diabetes as comorbidity if explicitly connected
            if profile.disease == "respiratory_viral_infection":
                if any(w in lower for w in ["comorbidity", "udakvah", "with diabetes", "diabetic comorbidity", "having diabetes"]):
                    comorbidities.append("diabetes")
            else:
                comorbidities.append("diabetes")
        if any(w in lower for w in ["cardiac", "heart", "hrudayavah", "hypertension", "bp fluctuation"]):
            comorbidities.append("cardiac")
        if any(w in lower for w in ["renal", "kidney", "mootravah", "gfr", "creatinine", "nephropathy"]):
            comorbidities.append("renal")
        if any(w in lower for w in ["annavah", "ibs", "ulcerative colitis", "gastrointestinal"]):
            comorbidities.append("gastrointestinal")
        if any(w in lower for w in ["asthma", "copd", "regular inhalers", "inhalers"]):
            comorbidities.append("asthma_copd")
        if any(w in lower for w in ["manovah", "anxiety", "insomnia"]):
            comorbidities.append("psychiatric")
        if any(w in lower for w in ["raktavah", "liver", "spleen"]):
            comorbidities.append("liver_spleen")

    profile.comorbidities = comorbidities
    profile.has_comorbidities = len(comorbidities) > 0

    # 5. Extract Symptoms
    symptom_tokens = ["cough", "kasa", "jwara", "fever", "shoth", "trushna", "aruchi", "pratishyaya", "shwasa", "dyspnea", "breathlessness"]
    for sym in symptom_tokens:
        if sym in lower:
            profile.symptoms.append(sym)

    # 6. Authoritative Table Resolution for Respiratory Viral Infection
    if profile.disease == "respiratory_viral_infection":
        if not profile.has_comorbidities:
            if profile.is_adult is not False:  # Adult or default
                if profile.severity == "mild":
                    profile.matched_table_name = "Pranvah Srotas vyadhi (Above 15 Years) - MILD (0 to 8) SpO2 above 94"
                    profile.matched_page = 17
                    profile.target_chunk_id = "DOC-FC76496810AB-0035-77484627D9DE"
                    profile.table_isolation_reason = (
                        "Patient is an adult (>=15 years) with mild respiratory viral infection (HRCT 0-8, SpO2 >94%) "
                        "and no comorbidities. Guidelines strictly specify the adult mild table on page 17."
                    )
                elif profile.severity == "moderate":
                    profile.matched_table_name = "Pranvah Srotas vyadhi (Above 15 Years) - MODERATE (9 to 15) SpO2 90 to 94"
                    profile.matched_page = 17
                    profile.target_chunk_id = "DOC-FC76496810AB-0035-77484627D9DE"
                    profile.table_isolation_reason = (
                        "Patient is an adult (>=15 years) with moderate respiratory viral infection (HRCT 9-15, SpO2 90-94%) "
                        "and no comorbidities. Guidelines strictly specify the adult moderate table on page 17."
                    )
                elif profile.severity == "severe":
                    profile.matched_table_name = "Pranvah Srotas vyadhi (Above 15 Years) - SEVERE (>15) SpO2 below 90"
                    profile.matched_page = 17
                    profile.target_chunk_id = "DOC-FC76496810AB-0036-20ED5DC46A3C"
                    profile.table_isolation_reason = (
                        "Patient is an adult (>=15 years) with severe respiratory viral infection (HRCT >15, SpO2 <90%) "
                        "and no comorbidities. Guidelines strictly specify the adult severe table on page 17."
                    )
            else:
                profile.matched_table_name = "Pranvah Srotas vyadhi (Below 15 Years)"
                profile.matched_page = 16
                profile.target_chunk_id = "DOC-FC76496810AB-0033-312CE552D1E5"
                profile.table_isolation_reason = "Patient is pediatric (<15 years). Guidelines specify page 16."
        elif "diabetes" in profile.comorbidities and len(profile.comorbidities) == 1:
            if profile.severity in ("mild", None):
                profile.matched_table_name = "Udakvah srotas vyadhi (Diabetes Mellitus) - MILD (0 to 8) SpO2 above 94"
                profile.matched_page = 14
                profile.target_chunk_id = "DOC-FC76496810AB-0028-4F2CFBD3E05E"
                profile.table_isolation_reason = (
                    "Patient has respiratory viral infection with Diabetes Mellitus comorbidity (Udakvah srotas). "
                    "Guidelines strictly specify the diabetes comorbidity table on page 14."
                )
            elif profile.severity == "severe":
                profile.matched_table_name = "Udakvah srotas vyadhi (Diabetes Mellitus) - SEVERE (>15) SpO2 below 90"
                profile.matched_page = 14
                profile.target_chunk_id = "DOC-FC76496810AB-0029-7C936491AE87"
                profile.table_isolation_reason = (
                    "Patient has severe respiratory viral infection with Diabetes Mellitus comorbidity. "
                    "Guidelines strictly specify the severe diabetes comorbidity table on page 14."
                )

    return profile


COMORBIDITY_SIGNATURE_MEDICINES = {
    "diabetes": ["sutendra", "sutendra rasayana", "meha rasayan", "meha rasayana"],
    "renal": ["heeraka", "heeraka rasayana", "heerak rasayan", "somkalpa"],
    "cardiac_psychiatric": ["pravi rasayana", "pravi rasayan"],
    "pediatric": ["bal rasayana", "bal rasayan", "rasvir"]
}


def is_chunk_applicable_for_profile(chunk: Dict[str, Any], profile: ClinicalProfile) -> Tuple[bool, str]:
    """
    Evaluates whether a retrieved chunk is clinically applicable to the patient profile,
    or if it belongs to an unapplicable comorbidity or mismatched age group table.
    """
    content = chunk.get("content", "")
    section = chunk.get("section", "")
    page = chunk.get("page")
    full_text = f"{section} {content}".lower()

    if profile.disease == "respiratory_viral_infection":
        # Check pediatric vs adult
        if profile.is_adult is True:
            if "below 15 years" in full_text and "above 15 years" not in full_text:
                return False, "Chunk is for pediatric patients (<15 years), but patient is an adult."
            if any(med in full_text for med in COMORBIDITY_SIGNATURE_MEDICINES["pediatric"]) and "above 15 years" not in full_text:
                return False, "Chunk contains pediatric formulations, but patient is an adult."

        if profile.is_adult is False:
            if "above 15 years" in full_text and "below 15 years" not in full_text:
                return False, "Chunk is for adult patients (>=15 years), but patient is pediatric."

        # Check comorbidities when patient has NO comorbidities
        if not profile.has_comorbidities:
            # Exclude explicit comorbidity headings
            if "udakvah srotas vyadhi (diabetes" in full_text or "diabetes mellitus" in full_text:
                if "pranvah srotas vyadhi (above 15 years)" not in full_text:
                    return False, "Chunk is specific to Diabetes Mellitus comorbidity (Udakvah srotas), but patient has no diabetes."

            if "mootravah srotas vyadhi (chronic" in full_text or "renal failure" in full_text:
                return False, "Chunk is specific to Renal Failure comorbidity (Mootravah srotas), but patient has no kidney disease."

            if "manovah srotas vyadhi" in full_text or "hrudayavah srotas vyadhi (cardiac" in full_text:
                return False, "Chunk is specific to Cardiac or Psychiatric comorbidities, but patient has neither."

            if "annavah srotas vyadhi (ibs" in full_text:
                return False, "Chunk is specific to Gastrointestinal comorbidity (Annavah srotas), but patient has no GI comorbidity."

            if "raktavah srotas (liver" in full_text:
                return False, "Chunk is specific to Liver/Spleen comorbidity, but patient has no hepatic comorbidity."

            # Exclude comorbidity-specific tables that lack the heading in their chunk
            # Chunk 40: contains Sutendra in mild row (Page 19 - Diabetes table)
            if any(med in full_text for med in COMORBIDITY_SIGNATURE_MEDICINES["diabetes"]) and "pranvah srotas vyadhi (above 15 years)" not in full_text:
                return False, "Chunk contains formulations for Diabetes comorbidity (Sutendra), but patient has no diabetes."

            # Chunk 43: contains Heeraka Rasayana in mild row (Page 20 - Renal table)
            if any(med in full_text for med in COMORBIDITY_SIGNATURE_MEDICINES["renal"]):
                return False, "Chunk contains formulations for Renal comorbidity (Heeraka Rasayana), but patient has no kidney disease."

            # Chunk 46: contains Pravi Rasayana in mild row (Page 21 - Cardiac/Anxiety table)
            if any(med in full_text for med in COMORBIDITY_SIGNATURE_MEDICINES["cardiac_psychiatric"]):
                return False, "Chunk contains formulations for Cardiac/Anxiety comorbidity (Pravi Rasayana), but patient has no cardiac or anxiety disorder."

    return True, "Applicable"


def prioritize_and_isolate_chunks(
    retrieved_chunks: List[Dict[str, Any]],
    profile: ClinicalProfile
) -> List[Dict[str, Any]]:
    """
    Filters and re-prioritizes retrieved chunks so that:
    1. If a specific target chunk (e.g. Page 17 Adult Mild table) is identified, it is ranked #1.
    2. Chunks from unapplicable comorbidity or age-incompatible tables are filtered out
       from the evidence context sent to generation.
    3. If filtering removes all chunks, loads the authoritative target chunk if available,
       or safely preserves the original chunks.
    """
    if not retrieved_chunks:
        return []

    # If no specific isolation rule is active, return chunks as-is
    if not profile.matched_table_name and not profile.table_isolation_reason and not profile.target_chunk_id:
        return retrieved_chunks

    applicable_chunks: List[Dict[str, Any]] = []
    excluded_chunks: List[Tuple[Dict[str, Any], str]] = []

    for c in retrieved_chunks:
        is_app, reason = is_chunk_applicable_for_profile(c, profile)
        if is_app:
            applicable_chunks.append(c)
        else:
            excluded_chunks.append((c, reason))

    # If a specific target chunk is identified for this profile, ensure it is included
    if profile.target_chunk_id:
        target_in_app = any(c.get("chunk_id") == profile.target_chunk_id for c in applicable_chunks)
        if not target_in_app:
            # Check if target chunk was in retrieved_chunks before filtering
            tc = next((c for c in retrieved_chunks if c.get("chunk_id") == profile.target_chunk_id), None)
            if not tc:
                # Fetch target chunk directly from storage
                try:
                    from app.rag.retrieval import get_retrieval_service
                    tc = get_retrieval_service().get_chunk_by_id(profile.target_chunk_id)
                except Exception as exc:
                    logger.error(f"Error fetching target chunk {profile.target_chunk_id}: {exc}")
            if tc:
                applicable_chunks.insert(0, dict(tc))

    if applicable_chunks:
        # Re-sort to place exact target chunk at rank 1 if specified
        if profile.target_chunk_id:
            target_chunks = [c for c in applicable_chunks if c.get("chunk_id") == profile.target_chunk_id]
            other_chunks = [c for c in applicable_chunks if c.get("chunk_id") != profile.target_chunk_id]
            applicable_chunks = target_chunks + other_chunks

        # Reassign 1-based ranks
        for idx, c in enumerate(applicable_chunks, 1):
            c["rank"] = idx

        return applicable_chunks

    # Fallback: preserve original if all were filtered
    return retrieved_chunks


def sanitize_prescribed_medicines(
    medicines: List[MedicineItem],
    profile: ClinicalProfile,
    evidence_chunks: List[Dict[str, Any]]
) -> List[MedicineItem]:
    """
    Ensures prescribed medicines:
    1. Strictly match the patient's severity and guideline table.
    2. Do NOT mix medicines from diabetes, cardiac, or other comorbidity tables when not applicable.
    3. Attach each medicine to ONLY its verified source document and page number.
    4. Strip internal chunk IDs and avoid multi-page bleeding.
    """
    if not medicines:
        return []

    # Map chunk IDs to their metadata (page, doc_name)
    chunk_map = {c.get("chunk_id"): c for c in evidence_chunks if c.get("chunk_id")}

    # Determine matched table key for respiratory viral infection
    matched_table_key = None
    if profile.disease == "respiratory_viral_infection":
        if not profile.has_comorbidities:
            if profile.is_adult is not False:
                if profile.severity == "mild":
                    matched_table_key = "adult_mild"
                elif profile.severity == "moderate":
                    matched_table_key = "adult_moderate"
                elif profile.severity == "severe":
                    matched_table_key = "adult_severe"
            else:
                matched_table_key = "pediatric_all"
        elif "diabetes" in profile.comorbidities and len(profile.comorbidities) == 1:
            if profile.severity in ("mild", None):
                matched_table_key = "resp_diabetes_mild"

    if matched_table_key and matched_table_key in RESPIRATORY_TABLE_MAP:
        target_info = RESPIRATORY_TABLE_MAP[matched_table_key]
        valid_formulation_names = set(target_info["medicines"])
        target_chunk_id = target_info["chunk_id"]

        sanitized: List[MedicineItem] = []
        for m in medicines:
            med_clean = re.sub(r'^[\*\-\•\d\.\s]+', '', m.medicine).strip()
            # Find closest canonical name in target table
            matched_canonical = None
            for vf in valid_formulation_names:
                if vf.lower() in med_clean.lower() or med_clean.lower() in vf.lower():
                    matched_canonical = vf
                    break

            if not matched_canonical:
                logger.info(f"Filtering out non-table formulation '{m.medicine}' for {matched_table_key}.")
                continue

            # Ensure exact canonical formulation name, Matra, Sahpaan, and Aushadh Kal from table
            exact_dose = target_info.get("doses", {}).get(matched_canonical, m.dose)
            exact_sahpaan = target_info.get("sahpaan", {}).get(matched_canonical, m.anupana)
            exact_timing = target_info.get("timing", {}).get(matched_canonical, m.timing)

            # Frequency based strictly on dose / Kal
            exact_frequency = m.frequency
            if exact_dose == "2-2-2":
                exact_frequency = "Three times a day"
            elif exact_dose in ("1-0-1", "0-1-1"):
                exact_frequency = "Twice daily"
            elif exact_dose in ("1-0-0", "0-0-1"):
                exact_frequency = "Once daily"
            elif exact_dose == "1-1-1":
                exact_frequency = "Three times a day"

            single_chunk_id = target_chunk_id if target_chunk_id in chunk_map else (
                m.supporting_chunk_ids[0] if m.supporting_chunk_ids else target_chunk_id
            )

            sanitized_item = MedicineItem(
                medicine=matched_canonical,
                dose=exact_dose,
                dosage_form=m.dosage_form or "Rasayana Formulation",
                route=m.route or "Oral",
                frequency=exact_frequency,
                timing=exact_timing,
                duration=m.duration,
                anupana=exact_sahpaan,
                special_instructions=m.special_instructions,
                supporting_chunk_ids=[single_chunk_id]
            )
            sanitized.append(sanitized_item)

        # Deduplicate while preserving order
        seen_names = set()
        deduped: List[MedicineItem] = []
        for s in sanitized:
            if s.medicine not in seen_names:
                seen_names.add(s.medicine)
                deduped.append(s)
        sanitized = deduped

        # If any required table medicines were missed by LLM, ensure full guideline protocol
        existing_names = {s.medicine for s in sanitized}
        for expected_med in target_info["medicines"]:
            if expected_med not in existing_names and target_chunk_id in chunk_map:
                dose = target_info.get("doses", {}).get(expected_med, "1-0-0")
                if dose == "2-2-2":
                    freq = "Three times a day"
                elif dose in ("1-0-1", "0-1-1"):
                    freq = "Twice daily"
                elif dose == "1-1-1":
                    freq = "Three times a day"
                else:
                    freq = "Once daily"

                sanitized.append(
                    MedicineItem(
                        medicine=expected_med,
                        dose=dose,
                        dosage_form="Rasayana Formulation",
                        route="Oral",
                        frequency=freq,
                        timing=target_info.get("timing", {}).get(expected_med),
                        duration=None,
                        anupana=target_info.get("sahpaan", {}).get(expected_med),
                        special_instructions=None,
                        supporting_chunk_ids=[target_chunk_id]
                    )
                )

        return sanitized

    # General case: ensure supporting_chunk_ids contains ONLY chunk(s) that actually mention this medicine
    pruned_medicines: List[MedicineItem] = []
    seen_names = set()
    for m in medicines:
        m.medicine = re.sub(r'^[\*\-\•\d\.\s]+', '', m.medicine).strip()
        med_lower = m.medicine.lower().strip()
        if med_lower in seen_names:
            continue
        seen_names.add(med_lower)

        matched_chunk_ids = []
        for cid in m.supporting_chunk_ids:
            chunk = chunk_map.get(cid)
            if chunk and med_lower in chunk.get("content", "").lower():
                matched_chunk_ids.append(cid)

        # If no chunk matched by string or all were pruned, keep only the first valid chunk
        if not matched_chunk_ids and m.supporting_chunk_ids:
            matched_chunk_ids = [m.supporting_chunk_ids[0]]
        elif not matched_chunk_ids and evidence_chunks:
            matched_chunk_ids = [evidence_chunks[0]["chunk_id"]]

        m.supporting_chunk_ids = matched_chunk_ids[:1]  # Strict 1-to-1 chunk citation
        pruned_medicines.append(m)

    return pruned_medicines
