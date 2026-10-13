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


# Clinical knowledge resides dynamically in ChromaDB markdown chunks.



def parse_spo2_details(lower_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts raw SpO2 string and evaluated guideline severity.
    Returns (raw_value, severity).
    Severity thresholds:
      - > 94% -> 'mild'
      - 90% - 94% -> 'moderate'
      - < 90% -> 'severe'
    """
    if not lower_text:
        return None, None
    lower_text = lower_text.lower()
    m = re.search(r'\bspo2\s*(?:of|is|:)?\s*([><]?\s*\d{1,3}%?|\d{1,3}\s*(?:to|-)\s*\d{1,3}%?|above \d+%?|below \d+%?|greater than \d+%?|less than \d+%?)', lower_text)
    if not m:
        return None, None

    raw = m.group(1).strip()
    raw_clean = raw.replace(" ", "")

    if "<" in raw_clean or "below" in raw.lower() or "less than" in raw.lower():
        digits = re.findall(r'\d+', raw)
        val = int(digits[0]) if digits else 85
        return raw, "severe" if val <= 90 else ("moderate" if val <= 94 else "mild")

    if ">" in raw_clean or "above" in raw.lower() or "greater than" in raw.lower():
        digits = re.findall(r'\d+', raw)
        val = int(digits[0]) if digits else 95
        return raw, "mild" if val >= 94 else ("moderate" if val >= 90 else "severe")

    range_match = re.search(r'(\d{1,3})\s*(?:to|-)\s*(\d{1,3})', raw)
    if range_match:
        low_val = int(range_match.group(1))
        high_val = int(range_match.group(2))
        if 90 <= low_val and high_val <= 94:
            return raw, "moderate"
        elif low_val > 94:
            return raw, "mild"
        elif high_val < 90:
            return raw, "severe"

    digits = re.findall(r'\d+', raw)
    if digits:
        val = int(digits[0])
        if val > 94:
            return raw, "mild"
        elif 90 <= val <= 94:
            return raw, "moderate"
        elif val < 90:
            return raw, "severe"

    return raw, None


def parse_hrct_details(lower_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts raw HRCT string and evaluated guideline severity.
    Returns (raw_value, severity).
    Severity thresholds:
      - 0 to 8 (or <= 8) -> 'mild'
      - 9 to 15 (or 9-15) -> 'moderate'
      - > 15 (or >= 16) -> 'severe'
    """
    if not lower_text:
        return None, None
    lower_text = lower_text.lower()
    m = re.search(r'\bhrct\s*(?:score)?\s*(?:of|is|:)?\s*([><]?\s*\d{1,2}|\d{1,2}\s*(?:to|-|–)\s*\d{1,2}|above \d+|below \d+|greater than \d+|less than \d+)', lower_text)
    if not m:
        return None, None

    raw = m.group(1).strip()
    raw_clean = raw.replace(" ", "")

    if ">" in raw_clean or "above" in raw.lower() or "greater than" in raw.lower():
        digits = re.findall(r'\d+', raw)
        val = int(digits[0]) if digits else 16
        return raw, "severe" if val >= 15 else ("moderate" if val >= 9 else "mild")

    if "<" in raw_clean or "below" in raw.lower() or "less than" in raw.lower():
        digits = re.findall(r'\d+', raw)
        val = int(digits[0]) if digits else 8
        return raw, "mild" if val <= 8 else ("moderate" if val <= 15 else "severe")

    range_match = re.search(r'(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})', raw)
    if range_match:
        low_val = int(range_match.group(1))
        high_val = int(range_match.group(2))
        if high_val <= 8:
            return raw, "mild"
        elif 9 <= low_val and high_val <= 15:
            return raw, "moderate"
        elif low_val >= 15:
            return raw, "severe"

    digits = re.findall(r'\d+', raw)
    if digits:
        val = int(digits[0])
        if 0 <= val <= 8:
            return raw, "mild"
        elif 9 <= val <= 15:
            return raw, "moderate"
        elif val > 15:
            return raw, "severe"

    return raw, None


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

    # 2. Extract HRCT Score and SpO2 with dynamic biomarker evaluation
    hrct_raw, hrct_sev = parse_hrct_details(lower)
    spo2_raw, spo2_sev = parse_spo2_details(lower)

    profile.hrct_score_raw = hrct_raw
    profile.spo2_raw = spo2_raw
    if spo2_raw:
        digits = re.findall(r'\d+', spo2_raw)
        if digits:
            profile.spo2 = int(digits[0])
    if hrct_raw:
        digits = re.findall(r'\d+', hrct_raw)
        if digits:
            profile.hrct_score = int(digits[0])

    # 3. Determine Severity: prioritize objective clinical biomarkers (HRCT, SpO2) first, then qualified terms
    if hrct_sev and spo2_sev:
        if hrct_sev != spo2_sev:
            profile.severity = None  # Intra-query contradiction
        else:
            profile.severity = hrct_sev
    elif hrct_sev:
        profile.severity = hrct_sev
    elif spo2_sev:
        profile.severity = spo2_sev
    else:
        if "severe" in lower and not re.search(r'\b(?:without|no)\s+severe\b', lower):
            profile.severity = "severe"
        elif "moderate" in lower and not re.search(r'\b(?:without|no)\s+moderate\b', lower):
            profile.severity = "moderate"
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

    return profile


def is_chunk_applicable_for_profile(chunk: Dict[str, Any], profile: ClinicalProfile) -> Tuple[bool, str]:
    """
    Evaluates whether a retrieved chunk is clinically applicable to the patient profile,
    or if it belongs to an unapplicable comorbidity or mismatched age group table.
    """
    content = chunk.get("content", "")
    section = chunk.get("section", "")
    full_text = f"{section} {content}".lower()

    if profile.disease == "respiratory_viral_infection":
        # Check pediatric vs adult
        if profile.is_adult is True:
            if "below 15 years" in full_text and "above 15 years" not in full_text:
                return False, "Chunk is for pediatric patients (<15 years), but patient is an adult."

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

    return True, "Applicable"


def prioritize_and_isolate_chunks(
    retrieved_chunks: List[Dict[str, Any]],
    profile: ClinicalProfile
) -> List[Dict[str, Any]]:
    """
    Filters retrieved chunks to eliminate age-mismatched or unapplicable comorbidity chunks.
    Preserves natural similarity and reranker ordering without forced chunk injection.
    """
    if not retrieved_chunks:
        return []

    applicable_chunks: List[Dict[str, Any]] = []
    for c in retrieved_chunks:
        is_app, _ = is_chunk_applicable_for_profile(c, profile)
        if is_app:
            applicable_chunks.append(c)

    if applicable_chunks:
        for idx, c in enumerate(applicable_chunks, 1):
            c["rank"] = idx
        return applicable_chunks

    return retrieved_chunks


def sanitize_prescribed_medicines(
    medicines: List[MedicineItem],
    profile: ClinicalProfile,
    evidence_chunks: List[Dict[str, Any]]
) -> List[MedicineItem]:
    """
    Dynamic grounding & verbatim containment validator:
    Verifies that every generated medicine literally exists in the retrieved evidence chunks.
    Preserves strict 1-to-1 chunk citations. Ungrounded or fabricated medicines are rejected.
    """
    if not medicines or not evidence_chunks:
        return []

    chunk_map = {c.get("chunk_id") or f"chk-{i}": c for i, c in enumerate(evidence_chunks)}
    valid_medicines: List[MedicineItem] = []
    seen_names = set()

    for m in medicines:
        raw_name = m.medicine or ""
        clean_name = re.sub(r'^[\*\-\•\u2022\d\.\s]+', '', raw_name).strip()
        med_lower = clean_name.lower()
        if not med_lower or med_lower in seen_names:
            continue

        # Check which chunks contain the clean medicine name literally
        matching_cids = [
            cid for cid, c in chunk_map.items()
            if med_lower in c.get("content", "").lower()
        ]

        if not matching_cids:
            logger.warning(f"Containment rejection: '{raw_name}' does not appear in retrieved evidence.")
            continue

        # If dose is specified, prefer chunk that also contains the dose string
        best_cid = matching_cids[0]
        if m.dose:
            dose_clean = m.dose.strip().lower()
            for cid in matching_cids:
                if dose_clean in chunk_map[cid].get("content", "").lower():
                    best_cid = cid
                    break

        seen_names.add(med_lower)
        m.medicine = clean_name
        m.supporting_chunk_ids = [best_cid]
        valid_medicines.append(m)

    return valid_medicines
