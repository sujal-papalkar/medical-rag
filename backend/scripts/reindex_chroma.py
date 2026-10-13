"""
Re-index ChromaDB Collection with Structure-Aware Table Chunks.

Loads chunks from backend/data/chunks/chunks.json, generates embeddings
via Google Gemini API (gemini-embedding-001, 768 dims), and indexes them
into the persistent ChromaDB collection 'medical_guidelines' in backend/chroma_db.
"""

import sys
import json
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from google import genai
from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import get_collection, get_chroma_client

logger = get_logger("reindex-chroma")


def reindex():
    print("=" * 70)
    print("RE-INDEXING CHROMADB FROM CHUNKS.JSON")
    print("=" * 70)

    chunks_file = settings.CHUNKS_PATH
    if not chunks_file.exists():
        raise FileNotFoundError(f"Chunks file not found at {chunks_file}")

    data = json.loads(chunks_file.read_text(encoding="utf-8"))
    all_chunks = data.get("chunks", data) if isinstance(data, dict) else data
    print(f"Total chunks in file: {len(all_chunks)}")

    # Filter out excluded chunks (e.g. boilerplate)
    active_chunks = [c for c in all_chunks if not c.get("exclude_from_embedding", False)]
    print(f"Active chunks to embed & index: {len(active_chunks)}")

    # Connect to ChromaDB
    collection = get_collection()
    initial_count = collection.count()
    print(f"Existing vector count in '{collection.name}': {initial_count}")

    # Clear existing vectors
    if initial_count > 0:
        print("Clearing existing vectors...")
        existing = collection.get()
        if existing and existing.get("ids"):
            collection.delete(ids=existing["ids"])
        print(f"Vectors after clearing: {collection.count()}")

    # Initialize Gemini client
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured!")
    genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Process in batches
    BATCH_SIZE = 20
    total_added = 0

    for i in range(0, len(active_chunks), BATCH_SIZE):
        batch = active_chunks[i:i + BATCH_SIZE]
        batch_ids = [c["chunk_id"] for c in batch]
        batch_docs = [c["content"] for c in batch]
        batch_metas = []

        for c in batch:
            meta = {
                "chunk_id": str(c.get("chunk_id", "")),
                "document_id": str(c.get("document_id", "")),
                "document_name": str(c.get("document_name", "")),
                "disease": str(c.get("disease", "")),
                "section": str(c.get("section", "")),
                "section_path": str(c.get("section_path", "")),
                "content_type": str(c.get("content_type", "")),
                "page": int(c.get("page") or 0),
                "table_id": str(c.get("table_id") or ""),
                "table_part": int(c.get("table_part") or 0),
                "table_total_parts": int(c.get("table_total_parts") or 0),
                "is_continuation": bool(c.get("is_continuation", False)),
                "comorbidity": str(c.get("comorbidity") or ""),
            }
            batch_metas.append(meta)

        print(f"Generating embeddings for batch {i // BATCH_SIZE + 1} ({len(batch)} chunks)...")
        res = genai_client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=batch_docs,
            config={"output_dimensionality": settings.EMBEDDING_DIMENSION}
        )
        batch_embeddings = [emb.values for emb in res.embeddings]

        print(f"Upserting batch {i // BATCH_SIZE + 1} into ChromaDB...")
        collection.add(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas,
            embeddings=batch_embeddings
        )
        total_added += len(batch)
        time.sleep(0.5)  # slight pause to avoid rate limits

    final_count = collection.count()
    print("=" * 70)
    print(f"RE-INDEXING COMPLETE! Total vectors in collection: {final_count}")
    print("=" * 70)


if __name__ == "__main__":
    reindex()
