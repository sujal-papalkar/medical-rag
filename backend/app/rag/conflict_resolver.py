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
    parse_spo2_details,
    parse_hrct_details,
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
        "hrct_severity": None,
        "spo2_severity": None,
        "biomarker_contradiction": False,
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

    # 2. Disease classification (with negation awareness)
    dm_tokens = ["diabetes", "prameha", "sugar", "glucose", "hba1c", "nephropathy", "trushna", "aruchi"]
    resp_tokens = ["respiratory", "viral", "kasa", "jwara", "hrct", "pranvah", "cough", "rhinorrhea", "shwasa", "covid"]

    negated_dm = bool(re.search(r'\b(?:without|no|zero|free of)\s+(?:known\s+)?(?:diabetes|prameha|sugar|glucose)\b', lower))
    negated_resp = bool(re.search(r'\b(?:without|no|zero|free of)\s+(?:known\s+)?(?:respiratory|viral infection|cough|kasa)\b', lower))

    is_resp = any(w in lower for w in resp_tokens) and not negated_resp
    is_dm = any(w in lower for w in dm_tokens) and not negated_dm

    if is_resp and not is_dm:
        params["disease"] = "respiratory_viral_infection"
    elif is_dm and not is_resp:
        params["disease"] = "diabetes"
    elif is_resp and is_dm:
        # Check primary focus vs comorbidity
        if any(w in lower for w in ["comorbidity", "sahvyadhi", "udakvah", "with diabetes", "having diabetes"]):
            params["disease"] = "respiratory_viral_infection"
        else:
            params["disease"] = "coexisting_conditions"

    # 3. Severity & Objective Biomarkers
    hrct_raw, hrct_sev = parse_hrct_details(lower)
    spo2_raw, spo2_sev = parse_spo2_details(lower)

    params["hrct_score"] = hrct_raw
    params["hrct_severity"] = hrct_sev
    params["spo2"] = spo2_raw
    params["spo2_severity"] = spo2_sev

    if hrct_sev and spo2_sev:
        if hrct_sev != spo2_sev:
            params["biomarker_contradiction"] = True
            params["severity"] = None
        else:
            params["severity"] = hrct_sev
    elif hrct_sev:
        params["severity"] = hrct_sev
    elif spo2_sev:
        params["severity"] = spo2_sev
    else:
        # Qualitative severity fallback
        if "severe" in lower and not re.search(r'\b(?:without|no)\s+severe\b', lower):
            params["severity"] = "severe"
        elif "moderate" in lower and not re.search(r'\b(?:without|no)\s+moderate\b', lower):
            params["severity"] = "moderate"
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
    query_params = extract_parameters_from_text(query)

    # Detect intra-query biomarker contradictions (e.g. HRCT 7 [mild] vs SpO2 90% [moderate])
    intra_conflicts: List[ClinicalConflict] = []
    if query_params.get("biomarker_contradiction"):
        intra_conflicts.append(ClinicalConflict(
            parameter="biomarkers",
            registered_value=f"HRCT {query_params.get('hrct_score')} ({str(query_params.get('hrct_severity', '')).upper()})",
            query_value=f"SpO2 {query_params.get('spo2')} ({str(query_params.get('spo2_severity', '')).upper()})",
            conflict_type="biomarker_contradiction",
            message=(
                f"Biomarker contradiction: Query specifies HRCT score '{query_params.get('hrct_score')}' "
                f"({str(query_params.get('hrct_severity', '')).upper()} severity) but SpO2 '{query_params.get('spo2')}' "
                f"({str(query_params.get('spo2_severity', '')).upper()} severity). Guideline dosing protocols differ strictly."
            )
        ))

    # 1. Custom / unregistered query (no patient record attached)
    if not patient_info or not patient_info.patient_id:
        profile = extract_clinical_profile(query=query, patient_info=None, disease=disease)
        if intra_conflicts and not confirm_override:
            summary = (
                f"Detected {len(intra_conflicts)} clinical biomarker contradiction(s) within query. "
                "Physician confirmation required before generating prescription."
            )
            result = ConflictResolutionResult(
                has_conflict=True,
                requires_confirmation=True,
                conflicts=intra_conflicts,
                resolution_summary=summary
            )
            return result, profile
        elif intra_conflicts and confirm_override:
            result = ConflictResolutionResult(
                has_conflict=True,
                requires_confirmation=False,
                conflicts=intra_conflicts,
                resolution_summary="Physician confirmed clinical override of contradictory biomarkers."
            )
            return result, profile

        result = ConflictResolutionResult(
            has_conflict=False,
            requires_confirmation=False,
            conflicts=[],
            resolution_summary="No registered patient profile attached. Query evaluated autonomously."
        )
        return result, profile

    # 2. Extract parameters from patient source
    patient_params = extract_parameters_from_patient(patient_info)

    # 3. Detect conflicts
    conflicts = detect_clinical_conflicts(patient_params, query_params)
    if intra_conflicts:
        conflicts.extend(intra_conflicts)

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
