import os
import json
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "medical_guidelines"

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768

TOP_K = 10

OUTPUT_DIR = Path("retrieval_results")
OUTPUT_DIR.mkdir(exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# CHROMADB
# ============================================================

chroma_client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH
)

collection = chroma_client.get_collection(
    COLLECTION_NAME
)

print("=" * 80)
print("CLINICAL RETRIEVAL TEST")
print("=" * 80)

print(f"Collection : {COLLECTION_NAME}")
print(f"Vectors    : {collection.count()}")
print(f"Top-K      : {TOP_K}")
print(f"Embedding  : {EMBEDDING_MODEL}")
print(f"Dimension  : {EMBEDDING_DIMENSION}")

print("=" * 80)


# ============================================================
# EMBEDDING FUNCTION
# ============================================================

def create_embedding(text: str):

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={
            "output_dimensionality": EMBEDDING_DIMENSION
        }
    )

    return response.embeddings[0].values


# ============================================================
# RETRIEVAL FUNCTION
# ============================================================

def retrieve(
    query: str,
    disease: str | None = None,
    top_k: int = TOP_K
):

    query_embedding = create_embedding(query)

    where_filter = None

    if disease:
        where_filter = {
            "disease": disease
        }

    if where_filter:

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

    else:

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

    return results


# ============================================================
# PRINT RESULTS
# ============================================================

def print_results(results, mode):

    print("\n")
    print("-" * 80)
    print(f"RETRIEVAL MODE: {mode}")
    print("-" * 80)

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for i in range(len(ids)):

        metadata = metadatas[i]

        print("\n" + "=" * 80)
        print(f"RANK       : {i + 1}")
        print(f"CHUNK ID   : {ids[i]}")
        print(f"DISTANCE   : {distances[i]}")
        print(f"DISEASE    : {metadata.get('disease')}")
        print(f"DOCUMENT   : {metadata.get('document_name')}")
        print(f"SECTION    : {metadata.get('section')}")
        print(f"CONTENT    : {metadata.get('content_type')}")
        print(f"PAGE       : {metadata.get('page')}")
        print("-" * 80)
        print("CONTENT:")
        print(documents[i])
        print("=" * 80)


# ============================================================
# CHECK WHETHER EXPECTED CONTENT WAS RETRIEVED
# ============================================================

def check_expected_content(
    results,
    expected_terms,
    test_name
):

    print("\n")
    print("-" * 80)
    print(f"EXPECTED CONTENT CHECK: {test_name}")
    print("-" * 80)

    all_content = []

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    for i in range(len(ids)):

        content = documents[i].lower()

        all_content.append({
            "rank": i + 1,
            "chunk_id": ids[i],
            "page": metadatas[i].get("page"),
            "content": content
        })

    combined_content = "\n".join(
        item["content"]
        for item in all_content
    )

    found_terms = []
    missing_terms = []

    for term in expected_terms:

        if term.lower() in combined_content:
            found_terms.append(term)
        else:
            missing_terms.append(term)

    print("\nExpected terms:")

    for term in expected_terms:

        if term in found_terms:
            print(f"  [FOUND]   {term}")
        else:
            print(f"  [MISSING] {term}")

    print("\nSummary:")
    print(f"Found   : {len(found_terms)}")
    print(f"Missing : {len(missing_terms)}")

    if missing_terms:

        print("\nMissing terms:")
        for term in missing_terms:
            print(f"  - {term}")

    else:

        print("\n[PASS] All expected terms were retrieved.")

    return {
        "found_terms": found_terms,
        "missing_terms": missing_terms
    }


# ============================================================
# TEST CASES
# ============================================================

TEST_CASES = [

    {
        "test_number": 1,
        "name": "Diabetes - Trushna Treatment",

        "query": (
            "A patient with Prameha or Diabetes mellitus has "
            "Trushna (polydipsia / excessive thirst). "
            "According to the guideline, retrieve the treatment "
            "information including medicine, Matra, Sahpaan "
            "and Aushadh Kal for Trushna."
        ),

        "disease": "diabetes",

        "expected_page": 8,

        "expected_terms": [
            "Trushna",
            "Polydipsia",
            "Zincare",
            "Kansya Rasayan",
            "2-0-2",
            "0-0-1",
            "Warm water",
            "Honey"
        ]
    },

    {
        "test_number": 2,
        "name": "Respiratory - Moderate Disease with Cardiac Comorbidity",

        "query": (
            "A patient with respiratory viral infection has "
            "cardiac comorbidity and moderate disease with "
            "HRCT score 9 to 15 and SpO2 90 to 94 percent. "
            "According to the guideline, retrieve the treatment "
            "including medicine, Matra, Sahpaan and Aushadh Kal."
        ),

        "disease": "respiratory_viral_infection",

        "expected_page": 15,

        "expected_terms": [
            "Rasavah Srotas",
            "Heart Diseases",
            "MODERATE",
            "9 to 15",
            "SpO2 90 to 94",
            "Somtajvir",
            "Pranvir",
            "Rasaka Rasayana",
            "Sutendra",
            "Arpisa Rasayan",
            "Heeraka Rasayana"
        ]
    }

]


# ============================================================
# RUN TESTS
# ============================================================

all_test_results = []


for test in TEST_CASES:

    print("\n\n")
    print("#" * 80)
    print(f"TEST CASE {test['test_number']}: {test['name']}")
    print("#" * 80)

    print("\nQUERY:")
    print(test["query"])

    print("\nEXPECTED SOURCE PAGE:")
    print(test["expected_page"])

    # --------------------------------------------------------
    # SEMANTIC ONLY
    # --------------------------------------------------------

    print("\n\n>>> SEMANTIC-ONLY RETRIEVAL")

    semantic_results = retrieve(
        query=test["query"],
        disease=None,
        top_k=TOP_K
    )

    print_results(
        semantic_results,
        "SEMANTIC ONLY"
    )

    semantic_check = check_expected_content(
        semantic_results,
        test["expected_terms"],
        f"{test['name']} - Semantic Only"
    )

    # --------------------------------------------------------
    # DISEASE FILTERED
    # --------------------------------------------------------

    print("\n\n>>> DISEASE-FILTERED RETRIEVAL")

    filtered_results = retrieve(
        query=test["query"],
        disease=test["disease"],
        top_k=TOP_K
    )

    print_results(
        filtered_results,
        "DISEASE FILTERED"
    )

    filtered_check = check_expected_content(
        filtered_results,
        test["expected_terms"],
        f"{test['name']} - Disease Filtered"
    )

    # --------------------------------------------------------
    # SAVE RESULTS
    # --------------------------------------------------------

    def convert_results(results):

        output = []

        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for i in range(len(ids)):

            metadata = metadatas[i]

            output.append({
                "rank": i + 1,
                "chunk_id": ids[i],
                "distance": distances[i],

                "disease": metadata.get("disease"),

                "document": metadata.get(
                    "document_name"
                ),

                "section": metadata.get(
                    "section"
                ),

                "content_type": metadata.get(
                    "content_type"
                ),

                "page": metadata.get(
                    "page"
                ),

                "content": documents[i]
            })

        return output

    test_result = {

        "test_number": test["test_number"],

        "test_name": test["name"],

        "query": test["query"],

        "expected_disease": test["disease"],

        "expected_source_page": test["expected_page"],

        "expected_terms": test["expected_terms"],

        "semantic_only": {

            "retrieval_mode": "semantic_only",

            "top_k": TOP_K,

            "results": convert_results(
                semantic_results
            ),

            "content_check": semantic_check
        },

        "disease_filtered": {

            "retrieval_mode": "disease_filtered",

            "filter": {
                "disease": test["disease"]
            },

            "top_k": TOP_K,

            "results": convert_results(
                filtered_results
            ),

            "content_check": filtered_check
        }
    }

    all_test_results.append(test_result)

    output_file = (
        OUTPUT_DIR
        / f"test_{test['test_number']:02d}.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            test_result,
            f,
            indent=2,
            ensure_ascii=False
        )

    print("\n")
    print("=" * 80)
    print(f"RESULT SAVED: {output_file}")
    print("=" * 80)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n\n")
print("#" * 80)
print("FINAL RETRIEVAL TEST SUMMARY")
print("#" * 80)

for result in all_test_results:

    print("\n")
    print(f"TEST {result['test_number']}: {result['test_name']}")

    semantic_found = len(
        result["semantic_only"]["content_check"]["found_terms"]
    )

    semantic_total = len(
        result["semantic_only"]["content_check"]["found_terms"]
    ) + len(
        result["semantic_only"]["content_check"]["missing_terms"]
    )

    filtered_found = len(
        result["disease_filtered"]["content_check"]["found_terms"]
    )

    filtered_total = len(
        result["disease_filtered"]["content_check"]["found_terms"]
    ) + len(
        result["disease_filtered"]["content_check"]["missing_terms"]
    )

    print(
        f"Semantic Only     : "
        f"{semantic_found}/{semantic_total} expected terms found"
    )

    print(
        f"Disease Filtered  : "
        f"{filtered_found}/{filtered_total} expected terms found"
    )

print("\n")
print("=" * 80)
print("TESTING COMPLETE")
print("=" * 80)