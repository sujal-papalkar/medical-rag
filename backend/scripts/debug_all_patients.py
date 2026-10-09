import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.repositories import PatientRepository
from app.rag.retrieval import get_retrieval_service
from app.rag.clinical_matcher import (
    extract_clinical_profile,
    prioritize_and_isolate_chunks,
    sanitize_prescribed_medicines,
    is_chunk_applicable_for_profile
)
from app.schemas.prescriptions import PatientInfo
from app.rag.generation import generate_structured_prescription

retrieval = get_retrieval_service()
patients = PatientRepository.list_patients()

print(f"Total registered patients: {len(patients)}")
for p in patients:
    pid = p["id"]
    query = p["clinical_query"]
    disease = p["disease"]
    p_info = PatientInfo(
        patient_id=pid,
        name=p["name"],
        age=p["age"],
        gender=p["gender"],
        disease=disease,
        presentation=p["presentation"]
    )

    print(f"\n=======================================================")
    print(f"PATIENT: {pid} - {p['name']} ({disease})")
    print(f"Query: {query}")
    
    # 1. Profile extraction
    profile = extract_clinical_profile(query=query, patient_info=p_info, disease=disease)
    print(f"Clinical Profile: age={profile.age}, is_adult={profile.is_adult}, severity={profile.severity}, comorbidities={profile.comorbidities}, matched_table={profile.matched_table_name}, target_chunk={profile.target_chunk_id}")

    # 2. ChromaDB search & Reranker
    raw_chunks = retrieval.retrieve(query=query, disease=disease, top_k=5)
    print(f"Chroma + Reranker returned {len(raw_chunks)} chunks:")
    for c in raw_chunks:
        app, reason = is_chunk_applicable_for_profile(c, profile)
        print(f"  * {c['chunk_id']} | Page {c['page']} | Applicable: {app} ({reason})")

    # 3. Filtered chunks
    isolated = prioritize_and_isolate_chunks(raw_chunks, profile)
    print(f"After prioritize_and_isolate_chunks: {len(isolated)} chunks:")
    for c in isolated:
        print(f"  * {c['chunk_id']} | Page {c['page']}")

    # 4. End-to-end generation call
    res = generate_structured_prescription(
        query=query,
        disease=disease,
        patient_info=p_info,
        top_k=5,
        num_candidates=1
    )
    print(f"Result Status: {res.status}")
    print(f"Prescribed medicines count: {len(res.medicines)}")
    for m in res.medicines:
        print(f"  - {m.medicine}: Dose={m.dose}, Timing={m.timing}, Sahpaan={m.anupana}, Chunks={m.supporting_chunk_ids}")
    if not res.medicines:
        print(f"  [!] ZERO MEDICINES RETURNED!")
        print(f"  Limitations: {res.limitations}")
        print(f"  Guidance: {res.clinical_guidance.guidance_summary}")
        print(f"  Recommendations: {res.clinical_guidance.key_recommendations}")
