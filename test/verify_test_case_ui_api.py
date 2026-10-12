"""
Test script to verify GET /api/v1/patients/test-cases and POST /api/v1/prescriptions/generate for Test Cases.
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    print("1. Testing GET /api/v1/patients/test-cases...")
    r = requests.get(f"{BASE_URL}/api/v1/patients/test-cases")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    test_cases = data.get("test_cases", [])
    print(f"   -> Retrieved {len(test_cases)} test cases.")
    assert len(test_cases) == 15, f"Expected 15 test cases, got {len(test_cases)}"
    
    tc3 = next((tc for tc in test_cases if tc["id"] == "TC-03"), None)
    assert tc3 is not None, "TC-03 not found"
    print(f"   -> TC-03: {tc3['name']}")
    print(f"      Expected Behavior: {tc3['expected_behavior']}")
    print(f"      Target Page: {tc3['supporting_source_page']}")
    print(f"      Pass Status: {tc3['pass_status']}")

    print("\n2. Testing POST /api/v1/prescriptions/generate for TC-03 (Paraphrased Query)...")
    payload = {
        "patient_id": "TC-03",
        "patient_info": {
            "patient_id": tc3["id"],
            "name": tc3["name"],
            "age": tc3["age"],
            "gender": tc3["gender"],
            "disease": tc3["disease"],
            "presentation": tc3["presentation"]
        },
        "query": tc3["clinical_query"],
        "disease": tc3["disease"],
        "top_k": 5
    }
    r = requests.post(f"{BASE_URL}/api/v1/prescriptions/generate", json=payload)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    presc = r.json()
    medicines = presc.get("medicines", [])
    print(f"   -> Prescribed {len(medicines)} formulations:")
    for m in medicines:
        citations = m.get("citations", [])
        pages = [c.get("page") for c in citations if c.get("page")]
        print(f"      * {m.get('name')}: Matra={m.get('dosage')}, Sahpaan={m.get('adjuvant')}, Kal={m.get('timing')}, Pages={pages}")
    
    print("\n3. Testing POST /api/v1/prescriptions/generate for TC-04 (Missing SpO2)...")
    tc4 = next((tc for tc in test_cases if tc["id"] == "TC-04"), None)
    payload4 = {
        "patient_id": "TC-04",
        "patient_info": {
            "patient_id": tc4["id"],
            "name": tc4["name"],
            "age": tc4["age"],
            "gender": tc4["gender"],
            "disease": tc4["disease"],
            "presentation": tc4["presentation"]
        },
        "query": tc4["clinical_query"],
        "disease": tc4["disease"],
        "top_k": 5
    }
    r4 = requests.post(f"{BASE_URL}/api/v1/prescriptions/generate", json=payload4)
    assert r4.status_code == 200, f"Expected 200, got {r4.status_code}: {r4.text}"
    presc4 = r4.json()
    print(f"   -> Limitations / Clinical Guidance: {presc4.get('limitations')}")
    print(f"   -> Prescribed {len(presc4.get('medicines', []))} formulations:")
    for m in presc4.get("medicines", []):
        print(f"      * {m.get('name')}: Matra={m.get('dosage')}")

    print("\n4. Testing POST /api/v1/prescriptions/generate for TC-10 (Comorbidity Udakvah)...")
    tc10 = next((tc for tc in test_cases if tc["id"] == "TC-10"), None)
    payload10 = {
        "patient_id": "TC-10",
        "patient_info": {
            "patient_id": tc10["id"],
            "name": tc10["name"],
            "age": tc10["age"],
            "gender": tc10["gender"],
            "disease": tc10["disease"],
            "presentation": tc10["presentation"]
        },
        "query": tc10["clinical_query"],
        "disease": tc10["disease"],
        "top_k": 5
    }
    r10 = requests.post(f"{BASE_URL}/api/v1/prescriptions/generate", json=payload10)
    assert r10.status_code == 200, f"Expected 200, got {r10.status_code}: {r10.text}"
    presc10 = r10.json()
    print(f"   -> Prescribed {len(presc10.get('medicines', []))} formulations:")
    for m in presc10.get("medicines", []):
        citations = m.get("citations", [])
        pages = [c.get("page") for c in citations if c.get("page")]
        print(f"      * {m.get('name')}: Matra={m.get('dosage')}, Pages={pages}")

    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
