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

    def retrieve(
        self,
        query: str,
        disease: Optional[str] = None,
        top_k: int = settings.DEFAULT_TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top_k chunks for a query:
        1. Embeds query.
        2. Retrieves Candidate Top-20 from ChromaDB.
        3. Reranks using the 70% Semantic + 30% Lexical composite reranker.
        """
        if not query or not query.strip():
            return []

        # 1. Query embedding
        query_embedding = self.create_embedding(query.strip())

        # 2. Disease filter
        where_filter = None
        if disease and disease.strip():
            where_filter = {"disease": disease.strip()}

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

            candidates.append({
                "rank": i + 1,
                "chunk_id": ids[i],
                "distance": dist,
                "document_name": meta.get("document_name", ""),
                "page": meta.get("page"),
                "disease": meta.get("disease", ""),
                "content_type": meta.get("content_type", ""),
                "section": meta.get("section", ""),
                "content": documents[i] if i < len(documents) else ""
            })

        # 4. Rerank candidates with 70% Semantic + 30% Lexical
        final_results = rerank_candidates(query=query, candidates=candidates, top_k=top_k)
        return final_results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full chunk details by ID from chunks cache."""
        if self._chunks_cache is None:
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

        return self._chunks_cache.get(chunk_id)


_service_instance: Optional[RetrievalService] = None


def get_retrieval_service() -> RetrievalService:
    """RetrievalService singleton accessor."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RetrievalService()
    return _service_instance
