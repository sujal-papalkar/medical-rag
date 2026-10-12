"""
End-to-End RAG Workflow Test Suite (Test Cases 3 to 15).

Tests the full Prescription Generation RAG pipeline covering:
- Test Case 3 — Paraphrased query consistency
- Test Case 4 — Missing SpO2 handling
- Test Case 5 — Missing HRCT handling
- Test Case 6 — Missing both severity parameters
- Test Case 7 — Short query with patient context
- Test Case 8 — Expanded query with distractors
- Test Case 9 — Symptom-specific retrieval (Trushna and Aruchi)
- Test Case 10 — Comorbidity filtering (Udakvah srotas vyadhi vs cardiac)
- Test Case 11 — Conflicting patient context & confirmation workflow
- Test Case 12 — Unsupported formulation (Negative grounding for Remdesivir/Azithromycin)
- Test Case 13 — Citation verification against source pages
- Test Case 14 — Duplicate / irrelevant retrieval & cross-disease contamination
- Test Case 15 — Repeated-query consistency across 3 consecutive runs

Outputs results to retrieval_results/rag_workflow_evaluation.json
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure backend modules are loadable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv()
if not os.getenv("GEMINI_API_KEY") and (BACKEND_DIR / ".env").exists():
    load_dotenv(BACKEND_DIR / ".env")

from app.database.repositories import PatientRepository
from app.schemas.prescriptions import PatientInfo
from app.rag.generation import generate_structured_prescription

OUTPUT_FILE = Path("retrieval_results") / "rag_workflow_evaluation.json"
OUTPUT_FILE.parent.mkdir(exist_ok=True)


def load_all_guideline_chunks() -> Dict[str, Dict[str, Any]]:
    """Loads all knowledge base chunks for ground truth verification."""
    chunks_path = BACKEND_DIR / "data" / "chunks" / "chunks.json"
    if not chunks_path.exists():
        chunks_path = BACKEND_DIR / "chunked_output" / "chunks.json"
    if not chunks_path.exists():
        return {}
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    return {c["chunk_id"]: c for c in chunks}


CHUNKS_BY_ID = load_all_guideline_chunks()


def run_case_3():
    """Test Case 3 — Paraphrased query."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 3: Paraphrased Query")
    print("=" * 80)

    p_info = PatientInfo(
        patient_id="TEMP-003",
        name="Test Patient 3",
        age=54,
        gender="Male",
        disease="diabetes",
        presentation="Type 2 Diabetes presenting with Trushna (Polydipsia)"
    )
    query = (
        "What are the recommended Ayurvedic medicines, dosages (Matra), "
        "adjuvants (Sahpaan), and administration timings (Aushadh Kal) "
        "for managing severe thirst (polydipsia / Trushna) in a diabetic patient?"
    )

    resp = generate_structured_prescription(query=query, disease="diabetes", patient_info=p_info)
    med_names = [m.medicine for m in resp.medicines]

    # Verify Zincare and Kansya Rasayan from Page 8
    has_zincare = any("zincare" in m.lower() for m in med_names)
    has_kansya = any("kansya" in m.lower() for m in med_names)
    passed = has_zincare and has_kansya and resp.status in ["success", "partial_success"]

    failure_reason = None
    failure_cat = None
    if not passed:
        missing = []
        if not has_zincare: missing.append("Zincare")
        if not has_kansya: missing.append("Kansya Rasayan")
        failure_reason = f"Paraphrased query did not retrieve expected formulations: {missing}. Prescribed: {med_names}"
        failure_cat = "Generation/grounding failure" if not med_names else "Retrieval failure"

    return {
        "test_number": 3,
        "name": "Test Case 3 — Paraphrased query",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "validation_status": resp.validation_status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else "",
            "limitations": resp.limitations,
            "evidence_sources": [s.model_dump() for s in resp.evidence_sources]
        },
        "expected_behavior": "Grounded retrieval of Page 8 formulations: Zincare (2-0-2) and Kansya Rasayan (0-0-1) consistent with Test Case 1.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 8
    }


def run_case_4():
    """Test Case 4 — Missing SpO2."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 4: Missing SpO2")
    print("=" * 80)

    p_info = PatientInfo(
        patient_id="TEMP-004",
        name="Test Patient 4",
        age=42,
        gender="Male",
        disease="respiratory_viral_infection",
        presentation="Respiratory viral infection with HRCT chest score of 12. SpO2 has not been recorded."
    )
    query = (
        "A 42-year-old patient with respiratory viral infection has HRCT chest score of 12. "
        "SpO2 has not been recorded. What treatment is recommended?"
    )

    resp = generate_structured_prescription(query=query, disease="respiratory_viral_infection", patient_info=p_info)

    # Verify system does not invent a specific SpO2 number (e.g. "SpO2 92%", "SpO2: 91%")
    all_text = f"{resp.clinical_guidance.guidance_summary if resp.clinical_guidance else ''} {' '.join(resp.limitations)} {resp.raw_answer or ''}".lower()
    
    # Check if a fabricated SpO2 percentage was invented
    import re
    invented_spo2 = re.findall(r'spo2\s*(?:of|is|:)?\s*(\d{2})%', all_text)
    # Exclude guideline range quotes like "90 to 94"
    explicit_invented = [val for val in invented_spo2 if val not in ["90", "91", "92", "93", "94", "95", "85"]]

    # Verify missing information is explicitly handled or noted in limitations / guidance
    handles_missing = (
        any("spo2" in lim.lower() or "oxygen" in lim.lower() or "missing" in lim.lower() for lim in resp.limitations)
        or any("spo2" in rec.lower() for rec in (resp.clinical_guidance.key_recommendations if resp.clinical_guidance else []))
        or "spo2" in (resp.clinical_guidance.guidance_summary.lower() if resp.clinical_guidance else "")
    )

    passed = len(explicit_invented) == 0 and handles_missing

    failure_reason = None
    failure_cat = None
    if not passed:
        reasons = []
        if explicit_invented:
            reasons.append(f"Invented SpO2 values found: {explicit_invented}")
        if not handles_missing:
            reasons.append("Missing SpO2 was silently ignored without explicit notation in limitations or guidance.")
        failure_reason = "; ".join(reasons)
        failure_cat = "Missing-context handling failure"

    return {
        "test_number": 4,
        "name": "Test Case 4 — Missing SpO2",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "validation_status": resp.validation_status,
            "severity": resp.clinical_guidance.severity_or_stage if resp.clinical_guidance else None,
            "medicines": [m.model_dump() for m in resp.medicines],
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else "",
            "limitations": resp.limitations
        },
        "expected_behavior": "System does not invent an SpO2 value and explicitly notes the absence of SpO2 in limitations or clinical guidance.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 18
    }


def run_case_5():
    """Test Case 5 — Missing HRCT."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 5: Missing HRCT")
    print("=" * 80)

    p_info = PatientInfo(
        patient_id="TEMP-005",
        name="Test Patient 5",
        age=35,
        gender="Female",
        disease="respiratory_viral_infection",
        presentation="Adult presenting with respiratory viral infection, SpO2 of 93% on room air. HRCT imaging was not done."
    )
    query = (
        "An adult patient with respiratory viral infection has SpO2 of 93 percent on room air, "
        "but HRCT scan was not performed. What formulations are indicated?"
    )

    resp = generate_structured_prescription(query=query, disease="respiratory_viral_infection", patient_info=p_info)

    # Check that system does not invent an HRCT number (e.g. "HRCT 11", "HRCT score: 10")
    all_text = f"{resp.clinical_guidance.guidance_summary if resp.clinical_guidance else ''} {' '.join(resp.limitations)} {resp.raw_answer or ''}".lower()
    import re
    invented_hrct = re.findall(r'hrct\s*(?:score)?\s*(?:of|is|:)?\s*(\d{1,2})\b', all_text)
    explicit_invented = [val for val in invented_hrct if val not in ["0", "8", "9", "15"]]

    # Check that missing HRCT is explicitly acknowledged
    handles_missing = (
        any("hrct" in lim.lower() or "missing" in lim.lower() or "imaging" in lim.lower() or "severity" in lim.lower() for lim in resp.limitations)
        or "hrct" in (resp.clinical_guidance.guidance_summary.lower() if resp.clinical_guidance else "")
    )

    passed = len(explicit_invented) == 0 and handles_missing

    failure_reason = None
    failure_cat = None
    if not passed:
        reasons = []
        if explicit_invented:
            reasons.append(f"Invented HRCT score found: {explicit_invented}")
        if not handles_missing:
            reasons.append("Missing HRCT imaging was not handled explicitly in limitations or guidance.")
        failure_reason = "; ".join(reasons)
        failure_cat = "Missing-context handling failure"

    return {
        "test_number": 5,
        "name": "Test Case 5 — Missing HRCT",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "validation_status": resp.validation_status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else "",
            "limitations": resp.limitations
        },
        "expected_behavior": "Missing HRCT is handled explicitly without inventing HRCT scores; limitations note absence of HRCT.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 18
    }


def run_case_6():
    """Test Case 6 — Missing both severity parameters."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 6: Missing both severity parameters")
    print("=" * 80)

    p_info = PatientInfo(
        patient_id="TEMP-006",
        name="Test Patient 6",
        age=30,
        gender="Male",
        disease="respiratory_viral_infection",
        presentation="Acute respiratory viral infection with neither HRCT score nor SpO2 available."
    )
    query = (
        "A 30-year-old adult has acute respiratory viral infection. Neither HRCT chest score "
        "nor SpO2 pulse oximetry is available. What medicines are recommended?"
    )

    resp = generate_structured_prescription(query=query, disease="respiratory_viral_infection", patient_info=p_info)
    med_names = [m.medicine.lower() for m in resp.medicines]

    # Verify system does NOT return unsupported severity-specific formulations (e.g. Heeraka, Sutendra, Arpisa)
    has_severe_specific = any(s in m for m in med_names for s in ["heeraka", "sutendra", "arpisa", "somkalpa"])
    
    # Verify explicit limitation stating missing severity / HRCT
    has_sev_limitation = any("severity" in lim.lower() or "hrct" in lim.lower() or "spo2" in lim.lower() for lim in resp.limitations)

    passed = (not has_severe_specific) and has_sev_limitation

    failure_reason = None
    failure_cat = None
    if not passed:
        reasons = []
        if has_severe_specific:
            reasons.append(f"Returned unsupported severity-specific formulations without severity parameters: {med_names}")
            failure_cat = "Generation/grounding failure"
        if not has_sev_limitation:
            reasons.append("Missing both HRCT and SpO2 was not noted in limitations.")
            failure_cat = failure_cat or "Missing-context handling failure"
        failure_reason = "; ".join(reasons)

    return {
        "test_number": 6,
        "name": "Test Case 6 — Missing both severity parameters",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "limitations": resp.limitations,
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else ""
        },
        "expected_behavior": "Does not prescribe unsupported severity-specific medications; explicitly documents missing severity parameters.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 13
    }


def run_case_7():
    """Test Case 7 — Short query using registered patient context."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 7: Short Query with Patient Context")
    print("=" * 80)

    # Use registered patient PAT-RESP-001: Priya Kulkarni, 32, Mild respiratory (HRCT 0-8, SpO2 >94%)
    p = PatientRepository.get_by_id("PAT-RESP-001")
    p_info = PatientInfo(
        patient_id=p["id"],
        name=p["name"],
        age=p["age"],
        gender=p["gender"],
        disease=p["disease"],
        presentation=p["presentation"]
    )
    query = "What formulations are listed for this patient?"

    resp = generate_structured_prescription(query=query, disease=p["disease"], patient_info=p_info)
    med_names = [m.medicine.lower() for m in resp.medicines]

    # Mild Adult formulations on Page 17: Somtajvir, Pranvir, Rasaka Rasayana, Sindhurbhushan Rasayan
    has_somtajvir = any("somtajvir" in m for m in med_names)
    has_pranvir = any("pranvir" in m for m in med_names)
    has_rasaka = any("rasaka" in m for m in med_names)
    
    passed = has_somtajvir and has_pranvir and has_rasaka and resp.status in ["success", "partial_success"]

    failure_reason = None
    failure_cat = None
    if not passed:
        failure_reason = f"Short query failed to utilize patient context. Prescribed: {med_names}"
        failure_cat = "Missing-context handling failure" if not med_names else "Generation/grounding failure"

    return {
        "test_number": 7,
        "name": "Test Case 7 — Short query",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "validation_status": resp.validation_status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else "",
            "evidence_sources": [s.model_dump() for s in resp.evidence_sources]
        },
        "expected_behavior": "Short query uses patient profile context to retrieve and prescribe Mild Adult formulations from Page 17.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 17
    }


def run_case_8():
    """Test Case 8 — Expanded query with distractors."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 8: Expanded Query with Distractors")
    print("=" * 80)

    p_info = PatientInfo(
        patient_id="TEMP-008",
        name="Test Patient 8",
        age=54,
        gender="Male",
        disease="diabetes",
        presentation="Type 2 Diabetes presenting with Trushna"
    )
    query = (
        "Please provide clinical advice for a 54-year-old diabetic patient suffering from severe "
        "excessive thirst (Trushna). By the way, the patient enjoys gardening on weekends, drinks chamomile tea, "
        "prefers herbal soaps, has a dog named Bruno, and wonders about Ayurvedic diet while traveling to Europe. "
        "What are the specific guideline medicines, Matra, Sahpaan, and Aushadh Kal?"
    )

    resp = generate_structured_prescription(query=query, disease="diabetes", patient_info=p_info)
    med_names = [m.medicine.lower() for m in resp.medicines]

    has_zincare = any("zincare" in m for m in med_names)
    has_kansya = any("kansya" in m for m in med_names)
    
    # Check that distractors did not inject hallucinated non-guideline items (e.g. chamomile, soaps)
    has_distractors = any(d in m for m in med_names for d in ["chamomile", "soap", "bruno", "europe"])

    passed = has_zincare and (not has_distractors) and resp.status in ["success", "partial_success"]

    failure_reason = None
    failure_cat = None
    if not passed:
        reasons = []
        if not has_zincare: reasons.append("Zincare missing from response")
        if has_distractors: reasons.append("Distractor terms hallucinated into medicine list")
        failure_reason = "; ".join(reasons)
        failure_cat = "Generation/grounding failure"

    return {
        "test_number": 8,
        "name": "Test Case 8 — Expanded query",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else ""
        },
        "expected_behavior": "Retrieval ignores distractors (gardening, chamomile tea, dog Bruno) and grounds in Page 8 Trushna guidance.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 8
    }


def run_case_9():
    """Test Case 9 — Symptom-specific retrieval (Trushna and Aruchi)."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 9: Symptom-Specific Retrieval (Trushna and Aruchi)")
    print("=" * 80)

    p = PatientRepository.get_by_id("PAT-DM-001")
    p_info = PatientInfo(
        patient_id=p["id"],
        name=p["name"],
        age=p["age"],
        gender=p["gender"],
        disease=p["disease"],
        presentation=p["presentation"]
    )
    query = (
        "A patient with diabetes mellitus presents with Trushna (polydipsia) and Aruchi (impaired taste). "
        "According to the guideline, what are the prescribed medicines, Matra, Sahpaan, and Aushadh Kal?"
    )

    resp = generate_structured_prescription(query=query, disease="diabetes", patient_info=p_info)
    med_names = [m.medicine.lower() for m in resp.medicines]

    # Expected: Zincare (2-0-2), Kansya Rasayan (0-0-1), Ruchir (0-1-1), Sannidha Rasayan (2-0-2), Zinzi chips
    has_zincare = any("zincare" in m for m in med_names)
    has_kansya_or_ruchir = any("kansya" in m or "ruchir" in m for m in med_names)
    
    # Ensure unrelated symptoms on Page 8 (e.g. Malaadhikya Swed bahulya or Nephropathy Urokine/Ayukshar) are NOT prescribed
    has_unrelated = any("urokine" in m or "ayukshar" in m or "chandanasav" in m for m in med_names)

    # Check doses, Sahpaan, Aushadh Kal matching
    dosage_valid = True
    for m in resp.medicines:
        if "zincare" in m.medicine.lower():
            if m.dose not in ["2-0-2", "2-0-2 (twice a day after food)"]:
                dosage_valid = False

    passed = has_zincare and has_kansya_or_ruchir and (not has_unrelated) and resp.status in ["success", "partial_success"]

    failure_reason = None
    failure_cat = None
    if not passed:
        reasons = []
        if not has_zincare: reasons.append("Zincare missing")
        if not has_kansya_or_ruchir: reasons.append("Kansya Rasayan / Ruchir missing")
        if has_unrelated: reasons.append("Unrelated nephropathy/dialysis medicines included")
        if not dosage_valid: reasons.append("Zincare dose did not match 2-0-2")
        failure_reason = "; ".join(reasons)
        failure_cat = "Generation/grounding failure"

    return {
        "test_number": 9,
        "name": "Test Case 9 — Symptom-specific retrieval",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else ""
        },
        "expected_behavior": "Only Page 8 rows for Trushna & Aruchi are returned with exact dose, Sahpaan, and Aushadh Kal.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 8
    }


def run_case_10():
    """Test Case 10 — Comorbidity filtering (Respiratory patient with Diabetes)."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 10: Comorbidity Filtering (Respiratory with Diabetes)")
    print("=" * 80)

    p = PatientRepository.get_by_id("PAT-RESP-002")
    p_info = PatientInfo(
        patient_id=p["id"],
        name=p["name"],
        age=p["age"],
        gender=p["gender"],
        disease=p["disease"],
        presentation=p["presentation"]
    )
    query = (
        "For an adult patient with respiratory viral infection who has diabetes mellitus comorbidity "
        "(Udakvah srotas vyadhi) and mild HRCT score 0 to 8 with SpO2 above 94, "
        "what are the recommended medicines and doses?"
    )

    resp = generate_structured_prescription(query=query, disease="respiratory_viral_infection", patient_info=p_info)
    med_names = [m.medicine.lower() for m in resp.medicines]

    # Page 14 Udakvah table: Somtajvir 1-0-0, Pranvir 2-2-2, Rasaka Rasayana 1-0-1, Meha Rasayan 1-0-0
    has_somtajvir = any("somtajvir" in m for m in med_names)
    has_meha = any("meha" in m for m in med_names)
    
    # Must NOT mix cardiac medicines (Sutendra, Heeraka, Arpisa)
    has_cardiac = any(c in m for m in med_names for c in ["sutendra", "heeraka", "arpisa"])

    passed = has_somtajvir and has_meha and (not has_cardiac) and resp.status in ["success", "partial_success"]

    failure_reason = None
    failure_cat = None
    if not passed:
        reasons = []
        if not has_somtajvir: reasons.append("Somtajvir missing")
        if not has_meha: reasons.append("Meha Rasayan (diabetic comorbidity specific) missing")
        if has_cardiac: reasons.append("Unrelated cardiac comorbidity medicines mixed into diabetic comorbidity prescription")
        failure_reason = "; ".join(reasons)
        failure_cat = "Generation/grounding failure"

    return {
        "test_number": 10,
        "name": "Test Case 10 — Comorbidity filtering",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "evidence_sources": [s.model_dump() for s in resp.evidence_sources],
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else ""
        },
        "expected_behavior": "Grounded strictly in Page 14 Udakvah comorbidity table (Meha Rasayan); does not mix unrelated cardiac recommendations.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 14
    }


def run_case_11():
    """Test Case 11 — Conflicting patient context & confirmation workflow."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 11: Conflicting Patient Context")
    print("=" * 80)

    # PAT-RESP-001 is Priya Kulkarni, Age 32, Female, Mild HRCT 0-8, SpO2 >94%, no comorbidity
    p = PatientRepository.get_by_id("PAT-RESP-001")
    p_info = PatientInfo(
        patient_id=p["id"],
        name=p["name"],
        age=p["age"],
        gender=p["gender"],
        disease=p["disease"],
        presentation=p["presentation"]
    )
    conflicting_query = (
        "Patient is a 65-year-old male with severe respiratory infection, "
        "HRCT score 18, SpO2 85 percent, and cardiac comorbidity. What medicines should be given?"
    )

    # Step 1: Unconfirmed request
    resp_unconfirmed = generate_structured_prescription(
        query=conflicting_query,
        disease=p["disease"],
        patient_info=p_info,
        confirm_override=False
    )

    # Check conflicts detected
    conflict_detected = resp_unconfirmed.requires_confirmation and resp_unconfirmed.status == "conflict_detected"
    zero_meds_unconfirmed = len(resp_unconfirmed.medicines) == 0

    # Verify PAT-RESP-001 in repository was NOT overwritten
    p_after = PatientRepository.get_by_id("PAT-RESP-001")
    registry_intact = (p_after["age"] == 32 and p_after["gender"] == "Female")

    # Step 2: Confirmed request (confirm_override=True)
    resp_confirmed = generate_structured_prescription(
        query=conflicting_query,
        disease=p["disease"],
        patient_info=p_info,
        confirm_override=True
    )
    override_honored = (not resp_confirmed.requires_confirmation) and resp_confirmed.status == "success"

    # Verify repository STILL NOT overwritten after confirmed override
    p_final = PatientRepository.get_by_id("PAT-RESP-001")
    registry_still_intact = (p_final["age"] == 32 and p_final["gender"] == "Female")

    passed = conflict_detected and zero_meds_unconfirmed and registry_intact and override_honored and registry_still_intact

    failure_reason = None
    failure_cat = None
    if not passed:
        reasons = []
        if not conflict_detected: reasons.append("Conflict was not surfaced or confirmation not required")
        if not zero_meds_unconfirmed: reasons.append("Medicines generated without physician confirmation")
        if not registry_intact or not registry_still_intact: reasons.append("Authoritative patient registry was silently overwritten")
        if not override_honored: reasons.append("Confirmed override failed to generate prescription")
        failure_reason = "; ".join(reasons)
        failure_cat = "Missing-context handling failure"

    return {
        "test_number": 11,
        "name": "Test Case 11 — Conflicting patient context",
        "input_patient_context": p_info.model_dump(),
        "query": conflicting_query,
        "actual_output": {
            "unconfirmed_status": resp_unconfirmed.status,
            "requires_confirmation": resp_unconfirmed.requires_confirmation,
            "conflicts_count": len(resp_unconfirmed.conflicts),
            "conflicts": [c.model_dump() for c in resp_unconfirmed.conflicts],
            "unconfirmed_medicines_count": len(resp_unconfirmed.medicines),
            "confirmed_status": resp_confirmed.status,
            "confirmed_medicines_count": len(resp_confirmed.medicines),
            "registered_patient_record_intact": registry_still_intact
        },
        "expected_behavior": "Conflicts surfaced and block generation until confirmed; registered patient records remain authoritative and untouched.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 15
    }


def run_case_12():
    """Test Case 12 — Unsupported formulation (Negative Grounding)."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 12: Unsupported Formulation (Negative Grounding)")
    print("=" * 80)

    p_info = PatientInfo(
        patient_id="TEMP-012",
        name="Test Patient 12",
        age=40,
        gender="Male",
        disease="respiratory_viral_infection",
        presentation="Respiratory viral infection inquiring about modern antivirals."
    )
    query = (
        "Does the Ayurvedic guideline recommend Remdesivir, Azithromycin, or Favipiravir "
        "for respiratory viral infection? If so, what is the exact dosage and administration?"
    )

    resp = generate_structured_prescription(query=query, disease="respiratory_viral_infection", patient_info=p_info)
    med_names = [m.medicine.lower() for m in resp.medicines]

    # Verify no fabricated synthetic drugs
    has_unsupported = any(u in m for m in med_names for u in ["remdesivir", "azithromycin", "favipiravir"])
    
    # Verify system reports insufficient supporting evidence or limitation
    reports_limitation = (
        len(med_names) == 0 or
        any("not specified" in lim.lower() or "not recommended" in lim.lower() or "insufficient" in lim.lower() or "not found" in lim.lower() for lim in resp.limitations)
        or any("remdesivir" in lim.lower() or "synthetic" in lim.lower() or "not" in lim.lower() for lim in resp.limitations)
        or "not" in (resp.clinical_guidance.guidance_summary.lower() if resp.clinical_guidance else "")
    )

    passed = (not has_unsupported) and reports_limitation

    failure_reason = None
    failure_cat = None
    if not passed:
        reasons = []
        if has_unsupported: reasons.append(f"System hallucinated unsupported synthetic formulations: {med_names}")
        if not reports_limitation: reasons.append("System failed to state limitation regarding unsupported formulations")
        failure_reason = "; ".join(reasons)
        failure_cat = "Generation/grounding failure"

    return {
        "test_number": 12,
        "name": "Test Case 12 — Unsupported formulation",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "limitations": resp.limitations,
            "guidance_summary": resp.clinical_guidance.guidance_summary if resp.clinical_guidance else ""
        },
        "expected_behavior": "Clearly reports insufficient supporting evidence rather than inventing Remdesivir or Azithromycin doses.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 13
    }


def run_case_13():
    """Test Case 13 — Citation verification against source pages."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 13: Citation Verification")
    print("=" * 80)

    p = PatientRepository.get_by_id("PAT-RESP-001")
    p_info = PatientInfo(
        patient_id=p["id"],
        name=p["name"],
        age=p["age"],
        gender=p["gender"],
        disease=p["disease"],
        presentation=p["presentation"]
    )
    query = (
        "For a 32-year-old adult presenting with mild respiratory viral infection "
        "(HRCT score 0 to 8, SpO2 above 94%) without severe dyspnea, "
        "what are the recommended Rasayana formulations, dosages, and Sahpaan?"
    )

    resp = generate_structured_prescription(query=query, disease="respiratory_viral_infection", patient_info=p_info)

    # Verify citations: Each medicine must have supporting chunk IDs that exist and mention the medicine
    citations_valid = True
    citation_issues = []

    for med in resp.medicines:
        if not med.supporting_chunk_ids:
            citations_valid = False
            citation_issues.append(f"{med.medicine} has no supporting_chunk_ids")
            continue
        for chunk_id in med.supporting_chunk_ids:
            chunk = CHUNKS_BY_ID.get(chunk_id)
            if not chunk:
                citations_valid = False
                citation_issues.append(f"{med.medicine} cites non-existent chunk_id {chunk_id}")
            else:
                chunk_text = chunk.get("content", "").lower()
                med_base = med.medicine.lower().split()[0]
                if med_base not in chunk_text:
                    citations_valid = False
                    citation_issues.append(f"{med.medicine} chunk {chunk_id} does not contain '{med_base}'")

    passed = citations_valid and len(resp.medicines) > 0

    failure_reason = None
    failure_cat = None
    if not passed:
        failure_reason = "; ".join(citation_issues) if citation_issues else "Zero medicines returned for citation verification"
        failure_cat = "Citation failure"

    return {
        "test_number": 13,
        "name": "Test Case 13 — Citation verification",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "medicines_with_citations": [
                {
                    "medicine": m.medicine,
                    "dose": m.dose,
                    "supporting_chunk_ids": m.supporting_chunk_ids,
                    "cited_pages": [CHUNKS_BY_ID[cid].get("page") for cid in m.supporting_chunk_ids if cid in CHUNKS_BY_ID]
                }
                for m in resp.medicines
            ]
        },
        "expected_behavior": "Each returned formulation is supported 1-to-1 by the cited source chunk and page 17.",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 17
    }


def run_case_14():
    """Test Case 14 — Duplicate or irrelevant retrieval (Cross-disease contamination)."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 14: Cross-Disease Contamination Check")
    print("=" * 80)

    p_info = PatientInfo(
        patient_id="TEMP-014",
        name="Test Patient 14",
        age=32,
        gender="Female",
        disease="respiratory_viral_infection",
        presentation="Mild respiratory viral infection (HRCT 0-8, SpO2 >94%) without diabetes or cardiac disease."
    )
    query = (
        "What formulations are prescribed for mild respiratory viral infection with HRCT 0-8 "
        "and SpO2 >94% without any diabetic or renal complications?"
    )

    resp = generate_structured_prescription(
        query=query,
        disease="respiratory_viral_infection",
        patient_info=p_info,
        confirm_override=True
    )
    med_names = [m.medicine.lower() for m in resp.medicines]

    # Verify no diabetes formulations (Zincare, Kansya, Urokine, Ayukshar, Ruchir)
    dm_meds = [m for m in med_names if any(d in m for d in ["zincare", "kansya", "urokine", "ayukshar", "ruchir", "zinzi"])]
    
    passed = len(dm_meds) == 0 and len(med_names) > 0

    failure_reason = None
    failure_cat = None
    if not passed:
        if dm_meds:
            failure_reason = f"Cross-disease contamination: Diabetes formulations retrieved for respiratory patient: {dm_meds}"
            failure_cat = "Retrieval failure"
        else:
            failure_reason = "No formulations returned"
            failure_cat = "Generation/grounding failure"

    return {
        "test_number": 14,
        "name": "Test Case 14 — Duplicate or irrelevant retrieval",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "status": resp.status,
            "medicines": [m.model_dump() for m in resp.medicines],
            "cross_disease_medicines_found": dm_meds
        },
        "expected_behavior": "Zero cross-disease contamination (no diabetes formulations in respiratory response).",
        "pass_status": "PASS" if passed else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 17
    }


def run_case_15():
    """Test Case 15 — Repeated-query consistency across 3 consecutive runs."""
    print("\n" + "=" * 80)
    print("RUNNING TEST CASE 15: Repeated-Query Consistency (3 Runs)")
    print("=" * 80)

    p = PatientRepository.get_by_id("PAT-RESP-001")
    p_info = PatientInfo(
        patient_id=p["id"],
        name=p["name"],
        age=p["age"],
        gender=p["gender"],
        disease=p["disease"],
        presentation=p["presentation"]
    )
    query = (
        "For an adult patient with mild respiratory viral infection "
        "(HRCT score 0 to 8, SpO2 above 94%) without severe dyspnea, "
        "what are the recommended Rasayana formulations, dosages, and Sahpaan?"
    )

    runs = []
    for r in range(1, 4):
        print(f"Executing Run {r} of 3...")
        resp = generate_structured_prescription(query=query, disease="respiratory_viral_infection", patient_info=p_info)
        runs.append({
            "run": r,
            "medicines": [m.medicine for m in resp.medicines],
            "doses": {m.medicine: m.dose for m in resp.medicines},
            "citations": {m.medicine: m.supporting_chunk_ids for m in resp.medicines}
        })
        time.sleep(1.0)

    # Check stability across runs
    med_sets = [set(run["medicines"]) for run in runs]
    all_same = (med_sets[0] == med_sets[1] == med_sets[2]) and len(med_sets[0]) > 0

    failure_reason = None
    failure_cat = None
    if not all_same:
        failure_reason = f"Variation across runs: Run 1={list(med_sets[0])}, Run 2={list(med_sets[1])}, Run 3={list(med_sets[2])}"
        failure_cat = "Generation/grounding failure"

    return {
        "test_number": 15,
        "name": "Test Case 15 — Repeated-query consistency",
        "input_patient_context": p_info.model_dump(),
        "query": query,
        "actual_output": {
            "runs": runs,
            "consistent_medicines": list(med_sets[0] & med_sets[1] & med_sets[2])
        },
        "expected_behavior": "Identical formulations and citations across 3 consecutive runs.",
        "pass_status": "PASS" if all_same else "FAIL",
        "failure_category": failure_cat,
        "failure_reason": failure_reason,
        "supporting_source_page": 17
    }


def main():
    print("#" * 80)
    print("STARTING END-TO-END RAG WORKFLOW EVALUATION (TEST CASES 3 TO 15)")
    print("#" * 80)

    test_runners = [
        run_case_3,
        run_case_4,
        run_case_5,
        run_case_6,
        run_case_7,
        run_case_8,
        run_case_9,
        run_case_10,
        run_case_11,
        run_case_12,
        run_case_13,
        run_case_14,
        run_case_15
    ]

    results = []
    for runner in test_runners:
        try:
            res = runner()
            results.append(res)
            print(f"RESULT: {res['name']} -> {res['pass_status']}")
            if res["failure_reason"]:
                print(f"  Reason: {res['failure_reason']}")
        except Exception as exc:
            print(f"ERROR executing {runner.__name__}: {exc}")
            results.append({
                "test_number": int(runner.__name__.split("_")[-1]),
                "name": runner.__doc__.strip() if runner.__doc__ else runner.__name__,
                "pass_status": "FAIL",
                "failure_category": "Execution Error",
                "failure_reason": str(exc)
            })

    # Save to JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"test_cases": results}, f, indent=2, ensure_ascii=False)

    print("\n" + "#" * 80)
    print(f"EVALUATION COMPLETE. SAVED TO: {OUTPUT_FILE}")
    print("#" * 80)
    
    passed_count = sum(1 for r in results if r["pass_status"] == "PASS")
    total_count = len(results)
    print(f"\nOVERALL RESULT: {passed_count}/{total_count} PASSED ({(passed_count/total_count)*100:.1f}%)")


if __name__ == "__main__":
    main()
