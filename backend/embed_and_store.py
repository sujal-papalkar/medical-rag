import json
import os
import time
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in .env")

INPUT_FILE = Path("chunked_output/chunks.json")
CHROMA_DIR = Path("chroma_db")
COLLECTION_NAME = "medical_guidelines"
EMBEDDING_MODEL = "gemini-embedding-001"
OUTPUT_DIMENSIONALITY = 768
BATCH_SIZE = 5
REQUEST_DELAY_SECONDS = 10
MAX_RETRIES = 6
INITIAL_RETRY_SECONDS = 15

client = genai.Client(api_key=GEMINI_API_KEY)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"description": "Medical guideline RAG knowledge base"},
)

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

with INPUT_FILE.open("r", encoding="utf-8") as f:
    chunks = json.load(f)

if not isinstance(chunks, list):
    raise ValueError("chunks.json must contain a list of chunks")

print(f"Loaded chunks: {len(chunks)}")

all_ids = [str(c["chunk_id"]) for c in chunks if c.get("chunk_id")]
existing_ids = set()
for start in range(0, len(all_ids), 5000):
    result = collection.get(ids=all_ids[start:start + 5000], include=[])
    existing_ids.update(result.get("ids", []))

print(f"Existing vectors: {len(existing_ids)}")

documents, ids, metadatas = [], [], []
metadata_updates = []

for chunk in chunks:
    chunk_id = str(chunk["chunk_id"])
    content = str(chunk.get("content", "")).strip()
    if not content:
        continue

    metadata = {
        "document_id": str(chunk.get("document_id", "")),
        "document_name": str(chunk.get("document_name", "")),
        "disease": str(chunk.get("disease", "")),
        "section": str(chunk.get("section") or ""),
        "content_type": str(chunk.get("content_type", "")),
    }
    if chunk.get("page") is not None:
        metadata["page"] = int(chunk["page"])

    # Existing vectors do not need to be re-embedded just because page
    # provenance changed. Refresh their metadata in-place.
    if chunk_id in existing_ids:
        metadata_updates.append((chunk_id, metadata))
        continue

    documents.append(content)
    ids.append(chunk_id)
    metadatas.append(metadata)

if metadata_updates:
    update_ids = [item[0] for item in metadata_updates]
    update_metadatas = [item[1] for item in metadata_updates]
    collection.update(ids=update_ids, metadatas=update_metadatas)
    print(f"Metadata refreshed (no re-embedding): {len(metadata_updates)}")

print(f"Already stored: {len(existing_ids)}")
print(f"Remaining to embed: {len(documents)}")

if not documents:
    print("Nothing to embed.")
    print(f"Chroma vectors: {collection.count()}")
    raise SystemExit(0)


def embed_batch(batch_documents):
    retry_seconds = INITIAL_RETRY_SECONDS
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch_documents,
                config={"output_dimensionality": OUTPUT_DIMENSIONALITY},
            )
            return [item.values for item in response.embeddings]
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code != 429:
                raise
            if attempt == MAX_RETRIES:
                raise
            print(f"429 quota/rate limit. Waiting {retry_seconds}s before retry ({attempt}/{MAX_RETRIES})...")
            time.sleep(retry_seconds)
            retry_seconds *= 2


total = len(documents)
for start in range(0, total, BATCH_SIZE):
    end = min(start + BATCH_SIZE, total)
    print(f"Embedding chunks {start + 1}-{end} of {total}...")
    embeddings = embed_batch(documents[start:end])
    if len(embeddings) != end - start:
        raise RuntimeError("Embedding count does not match document count.")
    collection.upsert(
        ids=ids[start:end],
        documents=documents[start:end],
        embeddings=embeddings,
        metadatas=metadatas[start:end],
    )
    print(f"Stored {end - start} chunks")
    if end < total:
        time.sleep(REQUEST_DELAY_SECONDS)

final_count = collection.count()
print()
print("=" * 50)
print("INGESTION COMPLETE")
print("=" * 50)
print(f"Collection        : {COLLECTION_NAME}")
print(f"Expected chunks   : {len(chunks)}")
print(f"Previously stored : {len(existing_ids)}")
print(f"Newly stored      : {total}")
print(f"Chroma vectors    : {final_count}")

# Verify page provenance stored in Chroma metadata.
all_stored = collection.get(include=["metadatas"])
stored_metadatas = all_stored.get("metadatas", [])
page_count = sum(m.get("page") is not None for m in stored_metadatas)
print(f"Chunks with page metadata: {page_count}/{final_count}")
print(f"Database          : {CHROMA_DIR.resolve()}")
print("=" * 50)
if final_count == len(chunks):
    print("Verification: ALL CHUNKS STORED SUCCESSFULLY.")
else:
    print(f"WARNING: expected {len(chunks)} vectors but ChromaDB contains {final_count}.")

if __name__ == "__main__":
    pass
