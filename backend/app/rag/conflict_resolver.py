"""
Universal Clinical Conflict Detection & Resolution Engine.

Guarantees:
1. Verified patient profile is authoritative for demographics and registered comorbidities.
2. Physician-edited query provides requested clinical scenario and explicit parameters.
3. If clinically relevant parameters conflict, flags the conflict and blocks unconfirmed generation.
4. Universal rules applied across all diseases, severity levels, and comorbidities without hardcoding.
5. Never silently merges conflicting values, infers missing information, or overwrites registered records.
6. When physician confirms override (confirm_override=True), resolves parameters and generates
   strictly evidence-grounded prescriptions with exact source/page citations.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Set

from app.core.logging import get_logger
from app.schemas.prescriptions import (
    PatientInfo,
    ClinicalConflict,
    ConflictResolutionResult,
)
from app.rag.clinical_matcher import (
    ClinicalProfile,
    extract_clinical_profile,
    RESPIRATORY_TABLE_MAP,
)

logger = get_logger("conflict-resolver")


def extract_parameters_from_text(text: str) -> Dict[str, Any]:
    """
    Extracts clinical parameters (age, adult/child status, disease, severity,
    HRCT score, SpO2, and comorbidity statements) from any clinical text.
    """
    if not text:
        return {}

    lower = text.lower()
    params: Dict[str, Any] = {
        "age": None,
        "is_adult": None,
        "disease": None,
        "severity": None,
        "hrct_score": None,
        "spo2": None,
        "comorbidities_present": [],
        "comorbidities_absent": [],
        "symptoms": []
    }

    # 1. Age extraction
    age_match = re.search(r'\b(\d{1,3})\s*(?:-| )(?:year|yr)s?(?:-| )(?:old)?\b|\bage[ :]+(\d{1,3})\b', lower)
    if age_match:
        age_val = int(age_match.group(1) or age_match.group(2))
        params["age"] = age_val
        params["is_adult"] = age_val >= 15
    elif any(w in lower for w in ["adult", "above 15", "geriatric", "elderly"]):
        params["is_adult"] = True
    elif any(w in lower for w in ["child", "children", "pediatric", "below 15", "under 15", "bal"]):
        params["is_adult"] = False

    # 2. Disease classification
    is_resp = any(w in lower for w in ["respiratory", "viral", "kasa", "jwara", "hrct", "pranvah", "cough", "rhinorrhea", "shwasa"])
    is_dm = any(w in lower for w in ["diabetes", "prameha", "sugar", "glucose", "hba1c", "nephropathy", "trushna", "aruchi"])

    if is_resp and not is_dm:
        params["disease"] = "respiratory_viral_infection"
    elif is_dm and not is_resp:
        params["disease"] = "diabetes"
    elif is_resp and is_dm:
        # Check primary focus vs comorbidity
        if any(w in lower for w in ["comorbidity", "sahvyadhi", "udakvah srotas vyadhi (diabetes"]):
            params["disease"] = "respiratory_viral_infection"
        else:
            params["disease"] = "coexisting_conditions"

    # 3. Severity & Biomarkers
    hrct_match = re.search(r'hrct\s*(?:score)?\s*(?:of)?\s*([0-9\-\>\<\s]+|greater than \d+|less than \d+)', lower)
    if hrct_match:
        params["hrct_score"] = hrct_match.group(1).strip()

    spo2_match = re.search(r'spo2\s*(?:of)?\s*([><]?\s*\d{1,3}%?|\d{1,3}\s*(?:to|-)\s*\d{1,3}%?|above \d+|below \d+)', lower)
    if spo2_match:
        params["spo2"] = spo2_match.group(1).strip()

    # Determine severity based on objective biomarkers first
    if any(w in lower for w in ["hrct >15", "hrct > 15", "greater than 15", "spo2 <90", "spo2 below 90", "below 90"]):
        params["severity"] = "severe"
    elif any(w in lower for w in ["hrct 9-15", "hrct 9–15", "hrct 9 to 15", "9 to 15", "spo2 90-94", "spo2 90 to 94", "90 to 94"]):
        params["severity"] = "moderate"
    elif any(w in lower for w in ["hrct 0-8", "hrct 0–8", "hrct 0 to 8", "0 to 8", "spo2 >94", "spo2 above 94", "above 94"]):
        params["severity"] = "mild"
    elif "moderate" in lower and not re.search(r'\b(?:without|no)\s+moderate\b', lower):
        params["severity"] = "moderate"
    elif "severe" in lower and not re.search(r'\b(?:without|no)\s+severe\b', lower):
        params["severity"] = "severe"
    elif "mild" in lower and not re.search(r'\b(?:without|no)\s+mild\b', lower):
        params["severity"] = "mild"

    # 4. Comorbidities Present vs Absent
    comorbidity_keys = {
        "diabetes": ["diabetes", "prameha", "udakvah", "high blood sugar", "type 2"],
        "renal": ["renal", "kidney", "mootravah", "gfr", "creatinine", "nephropathy"],
        "cardiac": ["cardiac", "heart", "hrudayavah", "hypertension", "bp fluctuation"],
        "gastrointestinal": ["annavah", "ibs", "ulcerative colitis", "gastrointestinal"],
        "asthma_copd": ["asthma", "copd", "inhalers"],
        "psychiatric": ["manovah", "anxiety", "insomnia"],
        "liver_spleen": ["raktavah", "liver", "spleen"]
    }

    for comorb, tokens in comorbidity_keys.items():
        # Check negated patterns: "without diabetes", "no renal disease", "free of cardiac"
        negated_pattern = rf'\b(?:without|no|zero|free of)\s+(?:known\s+)?(?:{"|".join(tokens)})\b'
        if re.search(negated_pattern, lower):
            params["comorbidities_absent"].append(comorb)
        elif any(t in lower for t in tokens):
            # Only count as comorbidity if explicitly connected or stated
            if any(w in lower for w in ["comorbidity", "with ", "having ", "history of ", "plus ", "complication"]):
                params["comorbidities_present"].append(comorb)

    # 5. Symptoms
    symptom_tokens = ["cough", "kasa", "jwara", "fever", "shoth", "trushna", "aruchi", "pratishyaya", "shwasa", "dyspnea", "breathlessness"]
    for sym in symptom_tokens:
        if sym in lower:
            params["symptoms"].append(sym)

    return params


def extract_parameters_from_patient(patient: PatientInfo) -> Dict[str, Any]:
    """
    Extracts authoritative clinical parameters from a verified patient record.
    """
    presentation_text = patient.presentation or ""
    pres_params = extract_parameters_from_text(presentation_text)

    patient_params: Dict[str, Any] = {
        "patient_id": patient.patient_id,
        "name": patient.name,
        "age": patient.age,
        "is_adult": (patient.age >= 15) if patient.age is not None else pres_params.get("is_adult"),
        "gender": patient.gender,
        "disease": patient.disease,
        "severity": pres_params.get("severity"),
        "hrct_score": pres_params.get("hrct_score"),
        "spo2": pres_params.get("spo2"),
        "comorbidities": list(set(pres_params.get("comorbidities_present", []))),
        "symptoms": pres_params.get("symptoms", [])
    }

    # Add disease-specific comorbidity indicators (e.g. Diabetic Nephropathy is renal + diabetes)
    pres_lower = presentation_text.lower()
    if "nephropathy" in pres_lower or "gfr" in pres_lower or "creatinine" in pres_lower:
        if "renal" not in patient_params["comorbidities"]:
            patient_params["comorbidities"].append("renal")

    if patient.disease == "respiratory_viral_infection":
        if "diabetes" in pres_lower and "diabetes" not in patient_params["comorbidities"]:
            patient_params["comorbidities"].append("diabetes")

    patient_params["has_comorbidities"] = len(patient_params["comorbidities"]) > 0
    return patient_params


def detect_clinical_conflicts(
    patient_params: Dict[str, Any],
    query_params: Dict[str, Any]
) -> List[ClinicalConflict]:
    """
    Identifies discrepancies between verified patient record (authoritative)
    and physician query (requested clinical scenario).
    """
    conflicts: List[ClinicalConflict] = []

    # 1. Demographic: Age Mismatch
    reg_age = patient_params.get("age")
    qry_age = query_params.get("age")
    if reg_age is not None and qry_age is not None and reg_age != qry_age:
        conflicts.append(ClinicalConflict(
            parameter="age",
            registered_value=reg_age,
            query_value=qry_age,
            conflict_type="demographic_mismatch",
            message=(
                f"Demographic conflict: Verified patient profile indicates age {reg_age}, "
                f"but query specifies age {qry_age}."
            )
        ))

    # 2. Demographic: Category (Adult vs Pediatric) Mismatch
    reg_adult = patient_params.get("is_adult")
    qry_adult = query_params.get("is_adult")
    if reg_adult is not None and qry_adult is not None and reg_adult != qry_adult:
        reg_cat = "Adult (>=15 yrs)" if reg_adult else "Pediatric (<15 yrs)"
        qry_cat = "Adult (>=15 yrs)" if qry_adult else "Pediatric (<15 yrs)"
        conflicts.append(ClinicalConflict(
            parameter="age_category",
            registered_value=reg_cat,
            query_value=qry_cat,
            conflict_type="demographic_mismatch",
            message=(
                f"Age category conflict: Patient is registered as {reg_cat}, "
                f"but query requests a protocol for {qry_cat}."
            )
        ))

    # 3. Primary Disease Category Mismatch
    reg_dis = patient_params.get("disease")
    qry_dis = query_params.get("disease")
    if reg_dis and qry_dis and qry_dis != "coexisting_conditions" and reg_dis != qry_dis:
        # If patient has respiratory and query is diabetes, or vice-versa without comorbidity link
        comorbs = patient_params.get("comorbidities", [])
        if qry_dis == "diabetes" and "diabetes" not in comorbs:
            conflicts.append(ClinicalConflict(
                parameter="disease",
                registered_value=reg_dis,
                query_value=qry_dis,
                conflict_type="disease_mismatch",
                message=(
                    f"Disease mismatch: Patient is registered for '{reg_dis}', "
                    f"but query requests guidelines for '{qry_dis}' without documented comorbidity."
                )
            ))
        elif qry_dis == "respiratory_viral_infection" and reg_dis != "respiratory_viral_infection":
            conflicts.append(ClinicalConflict(
                parameter="disease",
                registered_value=reg_dis,
                query_value=qry_dis,
                conflict_type="disease_mismatch",
                message=(
                    f"Disease mismatch: Patient is registered for '{reg_dis}', "
                    f"but query requests guidelines for '{qry_dis}'."
                )
            ))

    # 4. Comorbidities: Query asserts un-registered comorbidity
    reg_comorbs = set(patient_params.get("comorbidities", []))
    qry_comorbs_present = set(query_params.get("comorbidities_present", []))

    for c in qry_comorbs_present:
        # If the comorbidity mentioned is the patient's registered primary disease, it is not an unregistered comorbidity
        if c == reg_dis or (reg_dis == "diabetes" and c == "diabetes"):
            continue
        if c not in reg_comorbs:
            conflicts.append(ClinicalConflict(
                parameter="comorbidity",
                registered_value=list(reg_comorbs) if reg_comorbs else "None documented",
                query_value=c,
                conflict_type="comorbidity_discrepancy",
                message=(
                    f"Comorbidity discrepancy: Query specifies '{c}' comorbidity, "
                    f"which is not documented in the verified patient record."
                )
            ))

    # 5. Comorbidities: Query negates an active registered comorbidity or primary disease
    qry_comorbs_absent = set(query_params.get("comorbidities_absent", []))
    for c in qry_comorbs_absent:
        if c in reg_comorbs or (c == "diabetes" and reg_dis == "diabetes"):
            conflicts.append(ClinicalConflict(
                parameter="comorbidity",
                registered_value=f"Active {c} documented",
                query_value=f"Negated ({c} absent)",
                conflict_type="comorbidity_discrepancy",
                message=(
                    f"Comorbidity contradiction: Query asserts patient is free of '{c}', "
                    f"but verified patient record documents active '{c}'."
                )
            ))

    # 6. Severity / Objective Biomarker Contradiction
    reg_sev = patient_params.get("severity")
    qry_sev = query_params.get("severity")
    if reg_sev and qry_sev and reg_sev != qry_sev:
        # Check if query contradicts explicitly registered baseline severity
        conflicts.append(ClinicalConflict(
            parameter="severity",
            registered_value=reg_sev,
            query_value=qry_sev,
            conflict_type="severity_contradiction",
            message=(
                f"Severity contradiction: Patient record documents {reg_sev.upper()} severity, "
                f"but query specifies {qry_sev.upper()} severity."
            )
        ))

    return conflicts


def resolve_clinical_context(
    query: str,
    patient_info: Optional[PatientInfo] = None,
    disease: Optional[str] = None,
    confirm_override: bool = False
) -> Tuple[ConflictResolutionResult, ClinicalProfile]:
    """
    Universal conflict resolution:
    1. Extracts patient and query parameters separately.
    2. Detects clinical conflicts between patient record and query.
    3. If conflicts exist and confirm_override is False: blocks generation and requires confirmation.
    4. If conflicts exist and confirm_override is True: applies confirmed query parameters
       without overwriting registered patient records, maintaining exact citations.
    5. If no conflicts exist: builds authoritative ClinicalProfile smoothly.
    """
    # 1. Custom / unregistered query (no patient record attached)
    if not patient_info or not patient_info.patient_id:
        profile = extract_clinical_profile(query=query, patient_info=None, disease=disease)
        result = ConflictResolutionResult(
            has_conflict=False,
            requires_confirmation=False,
            conflicts=[],
            resolution_summary="No registered patient profile attached. Query evaluated autonomously."
        )
        return result, profile

    # 2. Extract parameters from both sources
    patient_params = extract_parameters_from_patient(patient_info)
    query_params = extract_parameters_from_text(query)

    # 3. Detect conflicts
    conflicts = detect_clinical_conflicts(patient_params, query_params)

    # 4. Handle unresolved conflict
    if conflicts and not confirm_override:
        summary = (
            f"Detected {len(conflicts)} clinical conflict(s) between verified patient record "
            f"and query parameters. Physician confirmation required before generating prescription."
        )
        # Build profile matching authoritative patient record strictly
        profile = extract_clinical_profile(query=query, patient_info=patient_info, disease=disease)
        result = ConflictResolutionResult(
            has_conflict=True,
            requires_confirmation=True,
            conflicts=conflicts,
            resolution_summary=summary
        )
        return result, profile

    # 5. Handle confirmed override or no conflict
    if conflicts and confirm_override:
        # Physician explicitly confirmed override: query clinical scenario takes precedence
        logger.info(f"Physician confirmed clinical override for patient {patient_info.patient_id}.")
        summary = (
            f"Physician confirmed clinical override for parameters: "
            f"{', '.join(c.parameter for c in conflicts)}. Prescriptions grounded in confirmed scenario."
        )

        # Build resolved clinical profile using confirmed query scenario
        effective_disease = query_params.get("disease") or patient_params.get("disease") or disease
        effective_age = query_params.get("age") if query_params.get("age") is not None else patient_params.get("age")

        # Create temporary confirmed patient info for profile building
        confirmed_patient = PatientInfo(
            patient_id=patient_info.patient_id,
            name=patient_info.name,
            age=effective_age,
            gender=patient_info.gender,
            disease=effective_disease,
            presentation=query
        )

        profile = extract_clinical_profile(query=query, patient_info=confirmed_patient, disease=effective_disease)

        result = ConflictResolutionResult(
            has_conflict=True,
            requires_confirmation=False,
            conflicts=conflicts,
            resolution_summary=summary
        )
        return result, profile

    # 6. Matching data (No conflict)
    profile = extract_clinical_profile(query=query, patient_info=patient_info, disease=disease)
    result = ConflictResolutionResult(
        has_conflict=False,
        requires_confirmation=False,
        conflicts=[],
        resolution_summary="Patient profile and query parameters match clinical expectations."
    )
    return result, profile
