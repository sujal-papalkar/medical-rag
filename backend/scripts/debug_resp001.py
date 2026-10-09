import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.retrieval import get_retrieval_service
from app.rag.reranking import compute_lexical_score

r = get_retrieval_service()
q = "For a patient presenting with mild respiratory viral infection (HRCT score 0 to 8, SpO2 above 94%) without severe dyspnea, what are the recommended Rasayana formulations, dosages, and Sahpaan?"

# Let's inspect ChromaDB Top-20
q_emb = r.create_embedding(q)
res = r.collection.query(
    query_embeddings=[q_emb],
    n_results=20,
    where={"disease": "respiratory_viral_infection"},
    include=["documents", "metadatas", "distances"]
)

ids = res["ids"][0]
metas = res["metadatas"][0]
dists = res["distances"][0]

print(f"ChromaDB returned {len(ids)} candidates for PAT-RESP-001:")
found_35 = False
for idx, (cid, meta, dist) in enumerate(zip(ids, metas, dists), 1):
    page = meta.get("page")
    if cid == "DOC-FC76496810AB-0035-77484627D9DE":
        found_35 = True
        print(f"==> FOUND Chunk 35 at Chroma Rank {idx}! Dist: {dist}, Page: {page}")
    else:
        if idx <= 8:
            print(f"  Rank {idx}: {cid} | Page {page} | Dist: {dist:.4f}")

if not found_35:
    print("==> Chunk 35 WAS NOT EVEN in ChromaDB Top-20 candidates!")

# Now let's check retrieve(q, top_k=10)
top_reranked = r.retrieve(q, disease="respiratory_viral_infection", top_k=10)
print(f"\nAfter 70/30 reranking (Top 10):")
for c in top_reranked:
    print(f"  Rank {c['rank']}: {c['chunk_id']} | Page {c['page']} | Dist: {c['distance']}")
