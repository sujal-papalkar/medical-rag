import chromadb
from dotenv import load_dotenv
from google import genai
import os

load_dotenv()

# ChromaDB
client_chroma = chromadb.PersistentClient(path="chroma_db")
collection = client_chroma.get_collection("medical_guidelines")

# Gemini
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

query = (
    "A patient with respiratory viral infection has "
    "Pranvah Srotas Vyadhi such as Asthma or COPD on regular inhalers. "
    "What Rasayana medicine, Matra, Sahpaan and Aushadh Kal are recommended?"
)

# Create query embedding
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents=query,
    config={"output_dimensionality": 768}
)

query_embedding = response.embeddings[0].values

# Retrieve
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    where={"disease": "respiratory_viral_infection"},
    include=["documents", "metadatas", "distances"]
)

print("\n" + "=" * 80)
print("TC-RESP-002 RETRIEVAL TEST")
print("=" * 80)

for i in range(len(results["ids"][0])):
    chunk_id = results["ids"][0][i]
    metadata = results["metadatas"][0][i]
    distance = results["distances"][0][i]

    print(f"\nRANK     : {i + 1}")
    print(f"CHUNK ID : {chunk_id}")
    print(f"DISTANCE : {distance}")
    print(f"PAGE     : {metadata.get('page')}")
    print(f"SECTION  : {metadata.get('section')}")
    print(f"TYPE     : {metadata.get('content_type')}")

    if chunk_id == "DOC-FC76496810AB-0022-E78671F0BE7D":
        print(">>> TARGET CHUNK FOUND <<<")

print("\n" + "=" * 80)