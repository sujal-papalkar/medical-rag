import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.repositories import PatientRepository
from app.rag.retrieval import get_retrieval_service
from app.rag.clinical_matcher import extract_clinical_profile, prioritize_and_isolate_chunks, is_chunk_applicable_for_profile

r = get_retrieval_service()
patients = [p for p in PatientRepository.list_patients() if p["disease"] == "diabetes"]

for p in patients:
    pid = p["id"]
    q = p["clinical_query"]
    print(f"\n=======================================================")
    print(f"PATIENT: {pid} - {p['name']}")
    print(f"Query: {q}")
    
    prof = extract_clinical_profile(q, disease="diabetes")
    print(f"Profile: disease={prof.disease}, severity={prof.severity}, comorbidities={prof.comorbidities}, matched_table={prof.matched_table_name}")

    chunks = r.retrieve(q, disease="diabetes", top_k=5)
    print(f"Retrieved {len(chunks)} chunks:")
    for c in chunks:
        app, reason = is_chunk_applicable_for_profile(c, prof)
        print(f"  * {c['chunk_id']} | Page {c['page']} | App: {app} ({reason})")
        print(f"    Section: {c.get('section')}")

    isolated = prioritize_and_isolate_chunks(chunks, prof)
    print(f"After isolation: {len(isolated)} chunks:")
    for c in isolated:
        print(f"  * {c['chunk_id']} | Page {c['page']}")
