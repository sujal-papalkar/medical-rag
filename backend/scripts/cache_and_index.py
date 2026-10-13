"""
Robust Re-index ChromaDB with Embedding Cache and Rate-Limit Handling.

Saves computed embeddings in backend/data/chunks/embedding_cache.json
so any API rate limits or interruptions never discard progress.
"""

import sys
import json
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from google import genai
from google.genai.errors import ClientError
from app.core.config import settings
from app.database.connection import get_collection

CACHE_FILE = BACKEND_DIR / "data" / "chunks" / "embedding_cache.json"


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")


def embed_with_retry(genai_client, texts: list, max_retries: int = 5) -> list:
    for attempt in range(max_retries):
        try:
            res = genai_client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=texts,
                config={"output_dimensionality": settings.EMBEDDING_DIMENSION}
            )
            return [e.values for e in res.embeddings]
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_time = 20 * (attempt + 1)
                print(f"[429 Rate Limit] Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                raise
        except Exception as e:
            if "429" in str(e):
                wait_time = 20 * (attempt + 1)
                print(f"[429 Rate Limit] Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                raise
    raise RuntimeError("Exceeded max retries for embedding.")


def main():
    print("=" * 70)
    print("ROBUST RE-INDEXING WITH EMBEDDING CACHE")
    print("=" * 70)

    chunks_file = settings.CHUNKS_PATH
    data = json.loads(chunks_file.read_text(encoding="utf-8"))
    all_chunks = data.get("chunks", data) if isinstance(data, dict) else data
    active_chunks = [c for c in all_chunks if not c.get("exclude_from_embedding", False)]
    print(f"Total active chunks to index: {len(active_chunks)}")

    cache = load_cache()
    print(f"Existing embeddings in cache: {len(cache)}")

    # Identify chunks needing embedding
    missing_chunks = [c for c in active_chunks if c["chunk_id"] not in cache]
    print(f"Chunks needing new embeddings: {len(missing_chunks)}")

    if missing_chunks:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing.")
        genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)

        BATCH_SIZE = 10
        for i in range(0, len(missing_chunks), BATCH_SIZE):
            batch = missing_chunks[i:i + BATCH_SIZE]
            batch_texts = [c["content"] for c in batch]
            print(f"Embedding batch {i // BATCH_SIZE + 1}/{(len(missing_chunks) + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch)} chunks)...")
            embeddings = embed_with_retry(genai_client, batch_texts)

            for c, emb in zip(batch, embeddings):
                cache[c["chunk_id"]] = emb

            save_cache(cache)
            time.sleep(4)  # 4 second spacing to respect rate limits

    print(f"All {len(active_chunks)} chunks have cached embeddings!")

    # Populate ChromaDB
    collection = get_collection()
    print(f"Clearing existing collection '{collection.name}'...")
    existing = collection.get()
    if existing and existing.get("ids"):
        collection.delete(ids=existing["ids"])

    batch_ids = []
    batch_docs = []
    batch_metas = []
    batch_embs = []

    for c in active_chunks:
        cid = c["chunk_id"]
        batch_ids.append(cid)
        batch_docs.append(c["content"])
        batch_embs.append(cache[cid])
        batch_metas.append({
            "chunk_id": str(cid),
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
        })

    print(f"Adding all {len(batch_ids)} chunks into ChromaDB...")
    # Add in batches of 50 to Chroma
    for i in range(0, len(batch_ids), 50):
        collection.add(
            ids=batch_ids[i:i + 50],
            documents=batch_docs[i:i + 50],
            metadatas=batch_metas[i:i + 50],
            embeddings=batch_embs[i:i + 50]
        )

    print("=" * 70)
    print(f"SUCCESS! ChromaDB collection '{collection.name}' now contains {collection.count()} vectors.")
    print("=" * 70)


if __name__ == "__main__":
    main()
