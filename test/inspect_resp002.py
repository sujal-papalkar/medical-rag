import chromadb
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import os

load_dotenv()

# -----------------------------
# CONFIG
# -----------------------------
TARGET_ID = "DOC-FC76496810AB-0022-E78671F0BE7D"

QUERY = (
    "A patient with respiratory viral infection has "
    "Pranvah Srotas Vyadhi such as Asthma or COPD on regular inhalers. "
    "What Rasayana medicine, Matra, Sahpaan and Aushadh Kal are recommended?"
)

# -----------------------------
# CLIENTS
# -----------------------------
db_path = "backend/chroma_db" if Path("backend/chroma_db").exists() else "chroma_db"
chroma = chromadb.PersistentClient(path=db_path)
collection = chroma.get_collection("medical_guidelines")

gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# -----------------------------
# EMBEDDING
# -----------------------------
response = gemini.models.embed_content(
    model="gemini-embedding-001",
    contents=QUERY,
    config={"output_dimensionality": 768}
)

query_embedding = response.embeddings[0].values

# -----------------------------
# RETRIEVE TOP 10
# -----------------------------
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    where={"disease": "respiratory_viral_infection"},
    include=["documents", "metadatas", "distances"]
)

ids = results["ids"][0]
documents = results["documents"][0]
metadatas = results["metadatas"][0]
distances = results["distances"][0]

# -----------------------------
# PRINT TOP 10
# -----------------------------
print("\n" + "=" * 100)
print("TC-RESP-002 — TOP 10 RETRIEVED CHUNKS")
print("=" * 100)

for i in range(len(ids)):

    print("\n" + "-" * 100)
    print(f"RANK       : {i + 1}")
    print(f"CHUNK ID   : {ids[i]}")
    print(f"DISTANCE   : {distances[i]}")
    print(f"PAGE       : {metadatas[i].get('page')}")
    print(f"TYPE       : {metadatas[i].get('content_type')}")
    print(f"SECTION    : {metadatas[i].get('section')}")

    print("\nCONTENT:")
    print(documents[i])

# -----------------------------
# GET TARGET CHUNK
# -----------------------------
print("\n\n" + "=" * 100)
print("TARGET CHUNK")
print("=" * 100)

target = collection.get(
    ids=[TARGET_ID],
    include=["documents", "metadatas"]
)

if target["ids"]:

    print(f"\nTARGET ID : {target['ids'][0]}")
    print(f"PAGE      : {target['metadatas'][0].get('page')}")
    print(f"TYPE      : {target['metadatas'][0].get('content_type')}")
    print(f"SECTION   : {target['metadatas'][0].get('section')}")

    print("\nTARGET CONTENT:")
    print(target["documents"][0])

else:
    print("TARGET CHUNK NOT FOUND!")

print("\n" + "=" * 100)
print("INSPECTION COMPLETE")
print("=" * 100)