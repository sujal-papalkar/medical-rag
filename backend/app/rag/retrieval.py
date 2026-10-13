"""
Candidate Retrieval & Vector Search Service.

Flow:
1. Generates query embedding using Gemini 'gemini-embedding-001' (768 dims).
2. Queries ChromaDB for Top-20 candidates (with optional disease filter).
3. Executes the 70% Semantic + 30% Lexical reranker.
4. Returns the Top-K evidence chunks.
"""

from typing import List, Dict, Any, Optional
import json
from google import genai

from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import get_collection
from app.rag.reranking import rerank_candidates

logger = get_logger("retrieval-service")


class RetrievalService:
    """Singleton service for embedding, vector search, and reranking."""

    DISEASE_ALIAS_MAP: Dict[str, str] = {
        "diabetes": "diabetes",
        "dm": "diabetes",
        "type 2 diabetes": "diabetes",
        "type 1 diabetes": "diabetes",
        "prameha": "diabetes",
        "respiratory": "respiratory_viral_infection",
        "respiratory_viral_infection": "respiratory_viral_infection",
        "respiratory viral infection": "respiratory_viral_infection",
        "cough": "respiratory_viral_infection",
        "kasa": "respiratory_viral_infection",
        "viral": "respiratory_viral_infection",
    }

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured in settings or environment.")

        self.genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.collection = get_collection()
        self._chunks_cache: Optional[Dict[str, Dict[str, Any]]] = None

    def create_embedding(self, text: str) -> List[float]:
        """Generates 768-dimensional text embedding."""
        response = self.genai_client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=text,
            config={"output_dimensionality": settings.EMBEDDING_DIMENSION}
        )
        return response.embeddings[0].values

    def _load_chunks_cache(self) -> None:
        chunks_path = settings.CHUNKS_PATH
        if chunks_path.exists():
            try:
                data = json.loads(chunks_path.read_text(encoding="utf-8"))
                chunk_list = data.get("chunks", data) if isinstance(data, dict) else data
                self._chunks_cache = {
                    c["chunk_id"]: c for c in chunk_list if "chunk_id" in c
                }
            except Exception as exc:
                logger.error(f"Error loading chunks cache: {exc}")
                self._chunks_cache = {}
        else:
            self._chunks_cache = {}

    def _aggregate_continuation_windows(
        self,
        final_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Contiguous chunk-window aggregation:
        When a table continuation chunk is retrieved, find and bundle related
        continuation chunks belonging to the same table window together.
        Ensures the complete table context and severity spectrum are present.
        """
        if not final_results:
            return []

        if self._chunks_cache is None:
            self._load_chunks_cache()

        if not self._chunks_cache:
            return final_results

        # Group cached chunks by table_id
        table_siblings: Dict[str, List[Dict[str, Any]]] = {}
        for c in self._chunks_cache.values():
            tid = c.get("table_id")
            if tid:
                table_siblings.setdefault(tid, []).append(c)

        for tid in table_siblings:
            table_siblings[tid].sort(key=lambda x: x.get("table_part", 1))

        retrieved_ids = {r["chunk_id"] for r in final_results if "chunk_id" in r}
        aggregated_results = list(final_results)

        for res in final_results:
            cid = res.get("chunk_id")
            chunk_detail = self._chunks_cache.get(cid, {}) if self._chunks_cache else {}
            tid = chunk_detail.get("table_id") or res.get("table_id")
            total_parts = chunk_detail.get("table_total_parts") or res.get("table_total_parts", 1)

            if tid and total_parts > 1 and tid in table_siblings:
                siblings = table_siblings[tid]
                for sib in siblings:
                    sib_id = sib.get("chunk_id")
                    if sib_id and sib_id not in retrieved_ids:
                        retrieved_ids.add(sib_id)
                        aggregated_results.append({
                            "rank": len(aggregated_results) + 1,
                            "chunk_id": sib_id,
                            "distance": res.get("distance", 0.0),
                            "document_name": sib.get("document_name", res.get("document_name", "")),
                            "page": sib.get("page", res.get("page")),
                            "disease": sib.get("disease", res.get("disease", "")),
                            "content_type": sib.get("content_type", "table"),
                            "section": sib.get("section", res.get("section", "")),
                            "content": sib.get("content", ""),
                            "table_id": tid,
                            "table_part": sib.get("table_part", 1),
                            "table_total_parts": total_parts,
                            "is_continuation_bundled": True,
                        })

        return aggregated_results

    def retrieve(
        self,
        query: str,
        disease: Optional[str] = None,
        top_k: int = settings.DEFAULT_TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top_k chunks for a query:
        1. Embeds query.
        2. Retrieves Candidate Top-20 from ChromaDB with canonical disease filter.
        3. Strictly filters candidates against canonical disease.
        4. Reranks using the 70% Semantic + 30% Lexical composite reranker.
        5. Performs contiguous continuation-window aggregation.
        """
        if not query or not query.strip():
            return []

        # 1. Query embedding
        query_embedding = self.create_embedding(query.strip())

        # 2. Disease filter canonicalization
        canonical_disease = None
        where_filter = None
        if disease and disease.strip():
            canonical_disease = self.DISEASE_ALIAS_MAP.get(disease.lower().strip(), disease.strip())
            where_filter = {"disease": canonical_disease}

        candidate_k = max(settings.RETRIEVAL_CANDIDATE_K, top_k)

        # 3. Chroma candidate search
        query_args = {
            "query_embeddings": [query_embedding],
            "n_results": candidate_k,
            "include": ["documents", "metadatas", "distances"]
        }
        if where_filter:
            query_args["where"] = where_filter

        results = self.collection.query(**query_args)

        ids = results["ids"][0] if results.get("ids") else []
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        candidates = []
        for i in range(len(ids)):
            meta = metadatas[i] if i < len(metadatas) else {}
            dist = round(float(distances[i]), 4) if i < len(distances) else None

            cand_disease = meta.get("disease", "")
            # Strict cross-disease post-filtering
            if canonical_disease and cand_disease != canonical_disease:
                continue

            candidates.append({
                "rank": i + 1,
                "chunk_id": ids[i],
                "distance": dist,
                "document_name": meta.get("document_name", ""),
                "page": meta.get("page"),
                "disease": cand_disease,
                "content_type": meta.get("content_type", ""),
                "section": meta.get("section", ""),
                "section_path": meta.get("section_path", ""),
                "comorbidity": meta.get("comorbidity", ""),
                "content": documents[i] if i < len(documents) else "",
                "table_id": meta.get("table_id"),
                "table_part": meta.get("table_part"),
                "table_total_parts": meta.get("table_total_parts"),
            })

        # 4. Rerank candidates with 70% Semantic + 30% Lexical
        final_results = rerank_candidates(query=query, candidates=candidates, top_k=top_k)

        # 5. Contiguous continuation-window aggregation
        final_results = self._aggregate_continuation_windows(final_results)

        return final_results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full chunk details by ID from chunks cache."""
        if self._chunks_cache is None:
            self._load_chunks_cache()
        return self._chunks_cache.get(chunk_id) if self._chunks_cache else None


_service_instance: Optional[RetrievalService] = None


def get_retrieval_service() -> RetrievalService:
    """RetrievalService singleton accessor."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RetrievalService()
    return _service_instance
